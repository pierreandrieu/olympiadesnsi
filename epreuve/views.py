from django.contrib.auth.models import User
from django.core.serializers import serialize
from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect, HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
from django.urls import reverse
from epreuve.models import Epreuve, Exercice, JeuDeTest, MembreComite, UserEpreuve, UserExercice
from epreuve.forms import ExerciceForm, AjoutOrganisateurForm
from epreuve.utils import redistribuer_jeux_de_test_exercice
from inscription.utils import assigner_participants_jeux_de_test, inscrire_groupe_a_epreuve
from inscription.models import GroupeParticipeAEpreuve, GroupeParticipant
import olympiadesnsi.decorators as decorators
import json
from datetime import timedelta
from typing import List, Optional, Dict


@login_required
@decorators.participant_inscrit_a_epreuve_required
def detail_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    """
    Affiche le détail d'une épreuve pour les participants inscrits.

    Utilise `epreuve_id` pour identifier l'épreuve et s'appuie sur le décorateur
    `participant_inscrit_a_epreuve_required` pour attacher l'objet épreuve correspondant
    à `request`. Assure que l'utilisateur est authentifié et inscrit à l'épreuve.

    Args:
        request (HttpRequest): La requête HTTP.
        epreuve_id (int): L'ID de l'épreuve à afficher.

    Returns:
        HttpResponse: La réponse HTTP avec le template d'affichage de l'épreuve.
    """
    epreuve: Epreuve = getattr(request, 'epreuve', None)
    return render(request, 'epreuve/detail_epreuve.html', {'epreuve': epreuve})


@login_required
@decorators.participant_inscrit_a_epreuve_required
def afficher_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    """
    Affiche les détails d'une épreuve pour un participant inscrit, incluant les exercices associés
    et le temps restant si l'épreuve est limitée dans le temps.

    La fonction filtre les exercices en fonction du mode de l'épreuve (tous les exercices ou un par un)
    et prépare les données pour affichage dans un format JSON utilisé par le frontend.

    Args:
        request (HttpRequest): La requête HTTP reçue.
        epreuve_id (int): L'identifiant de l'épreuve concernée.

    Returns:
        HttpResponse: La réponse HTTP avec le rendu du template `afficher_epreuve.html`.
    """
    # Récupération de l'utilisateur connecté et de l'épreuve depuis le décorateur.
    user: User = request.user
    epreuve: Optional[Epreuve] = getattr(request, 'epreuve', None)

    # Sélection de tous les exercices associés à l'épreuve, ordonnés par leur numéro.
    exercices: List[Exercice] = list(Exercice.objects.filter(epreuve=epreuve).order_by('numero'))

    # Si l'épreuve impose de passer les exercices un par un, filtrer pour ne garder que le premier non complété.
    if epreuve and epreuve.exercices_un_par_un:
        for ex in exercices:
            user_exercice, _ = UserExercice.objects.get_or_create(exercice=ex, participant=user)
            if not user_exercice.solution_instance_participant and not user_exercice.code_participant:
                exercices = [ex]
                break

    # Préparation des données des exercices pour le frontend.
    exercices_json_list: List[Dict[str, object]] = []
    for ex in exercices:
        user_exercice, _ = UserExercice.objects.get_or_create(exercice=ex, participant=user)
        jeu_de_test: Optional[JeuDeTest] = user_exercice.jeu_de_test

        exercice_dict: Dict[str, object] = {
            'id': ex.id,
            'titre': ex.titre,
            'bareme': ex.bareme,
            'enonce': ex.enonce,
            'enonce_code': ex.enonce_code,
            'type_exercice': ex.type_exercice,
            'avec_jeu_de_test': ex.avec_jeu_de_test,
            'code_a_soumettre': ex.code_a_soumettre,
            'nb_soumissions': user_exercice.nb_soumissions,
            'nb_max_soumissions': ex.nombre_max_soumissions,
            'retour_en_direct': ex.retour_en_direct,
            'instance_de_test': jeu_de_test.instance if jeu_de_test else "",
            'reponse_valide': user_exercice.solution_instance_participant == (
                jeu_de_test.reponse if jeu_de_test else "")
        }

        exercices_json_list.append(exercice_dict)

    # Conversion des données des exercices en JSON pour utilisation côté client.
    exercices_json: str = json.dumps(exercices_json_list)

    # Calcul du temps restant pour compléter l'épreuve, si applicable.
    temps_restant: Optional[timedelta] = None
    if epreuve and epreuve.temps_limite:
        user_epreuve, _ = UserEpreuve.objects.get_or_create(participant=user, epreuve=epreuve)
        if not user_epreuve.fin_epreuve:
            # Convertit la durée de l'épreuve en minutes en un objet timedelta
            user_epreuve.fin_epreuve = timezone.now() + timedelta(minutes=epreuve.duree)
            user_epreuve.save()

        # Calcul du temps restant
        temps_restant = max(user_epreuve.fin_epreuve - timezone.now(), timedelta(seconds=0))

    return render(request, 'epreuve/afficher_epreuve.html', {
        'epreuve': epreuve,
        'exercices_json': exercices_json,
        'temps_restant': temps_restant
    })


@login_required
@csrf_protect
@ratelimit(key='user', rate='10/m', block=True)
@ratelimit(key='user', rate='2/s', block=True)
def soumettre(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            exercice_id = data.get('exercice_id')
            code_soumis = data.get('code_soumis', "")
            solution_instance = data.get('solution_instance', "")

            #  Exercice et le jeu de test associé
            try:
                exercice = Exercice.objects.get(id=exercice_id)
                jeu_de_test = JeuDeTest.objects.filter(exercice=exercice).first()
            except (Exercice.DoesNotExist, JeuDeTest.DoesNotExist):
                return JsonResponse({'success': False, 'error': 'Exercice ou jeu de test introuvable'}, status=404)

            # Association UserExercice
            user_exercice = UserExercice.objects.get(
                participant=request.user,
                exercice=exercice
            )
            if user_exercice.nb_soumissions >= exercice.nombre_max_soumissions:
                return JsonResponse({'success': False, 'error': 'Nombre maximum de soumissions atteint'}, status=403)

            # Mise à jour des champs
            user_exercice.code_participant = code_soumis
            user_exercice.solution_instance_participant = solution_instance
            user_exercice.nb_soumissions += 1
            user_exercice.save()

            # Vérification de la solution
            reponse_valide = solution_instance == jeu_de_test.reponse if jeu_de_test else False

            return JsonResponse({'success': True, 'reponse_valide': reponse_valide})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Données invalides'}, status=400)
    else:
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)


@login_required
@decorators.administrateur_epreuve_required
def supprimer_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    epreuve: Epreuve = getattr(request, 'epreuve', None)
    if request.method == "POST":
        epreuve.delete()
        return redirect('espace_organisateur')
    return redirect('espace_organisateur')


@login_required
@decorators.membre_comite_required
def visualiser_epreuve_organisateur(request, epreuve_id):
    epreuve: Epreuve = getattr(request, 'epreuve', None)
    exercices: QuerySet[Exercice] = Exercice.objects.filter(epreuve=epreuve).order_by('numero')
    exercices_json = json.loads(serialize('json', exercices))

    return render(request, 'epreuve/visualiser_epreuve.html', {
        'epreuve': epreuve,
        'exercices_json': json.dumps(exercices_json)
    })


@login_required
@decorators.administrateur_epreuve_required
def ajouter_organisateur(request: HttpRequest, epreuve_id: int):
    """
    Vue pour ajouter un organisateur au comité d'organisation d'une épreuve.

    Cette vue permet à un administrateur d'épreuve de rajouter un nouvel organisateur
    au comité d'organisation de l'épreuve spécifiée. Elle effectue des vérifications pour
    s'assurer que l'utilisateur à ajouter existe, est éligible pour devenir organisateur,
    et n'est pas déjà membre du comité d'organisation.

    Args:
        request (HttpRequest): L'objet HttpRequest.
        epreuve_id (int): L'identifiant de l'épreuve pour laquelle un organisateur est ajouté.

    Returns:
        HttpResponseRedirect: Redirige vers l'espace organisateur si l'ajout est réussi.
        HttpResponse: Rend le template de l'espace organisateur avec le formulaire d'ajout en cas d'erreurs.
    """
    # L'objet épreuve est récupéré par le décorateur 'administrateur_epreuve_required'
    epreuve: Epreuve = getattr(request, 'epreuve', None)

    # Initialisation du formulaire avec les données POST et des informations supplémentaires
    form: AjoutOrganisateurForm = AjoutOrganisateurForm(request.POST or None,
                                                        epreuve=epreuve,
                                                        request_user=request.user)

    if request.method == "POST" and form.is_valid():
        # Si le formulaire est valide, procéder à l'ajout de l'organisateur
        username: str = form.cleaned_data['username']
        organisateur_a_ajouter: User = User.objects.get(username=username)

        # Création de l'entrée MembreComite pour associer l'organisateur à l'épreuve
        MembreComite.objects.create(epreuve=epreuve, membre=organisateur_a_ajouter)

        # Envoi d'un message de succès à l'utilisateur
        messages.success(request, f"{username} a bien été ajouté au comité d'organisation de l'épreuve {epreuve.nom}")

        # Redirection vers l'espace organisateur après l'ajout
        return HttpResponseRedirect(reverse('espace_organisateur'))

    # Si la méthode n'est pas POST ou que le formulaire n'est pas valide, rendre le template avec le formulaire
    return render(request, 'intranet/espace_organisateur.html', {'form': form})


@login_required
@decorators.administrateur_epreuve_required
def inscrire_groupes_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    """
    Inscrit des groupes de participants à une épreuve donnée, en vérifiant que l'utilisateur est un administrateur
    de l'épreuve. Cette vue permet de sélectionner plusieurs groupes pour les inscrire à une épreuve spécifique.

    Args:
        request (HttpRequest): L'objet requête HTTP.
        epreuve_id (int): L'ID de l'épreuve à laquelle les groupes seront inscrits.

    Returns:
        HttpResponse: L'objet réponse HTTP pour rediriger ou afficher la page.
    """
    epreuve: Epreuve = getattr(request, 'epreuve', None)  # Épreuve récupérée par le décorateur.

    if request.method == 'POST':
        groupe_ids: List[int] = request.POST.getlist('groups')  # IDs des groupes sélectionnés pour l'inscription.
        with transaction.atomic():
            for groupe_id in groupe_ids:
                groupe: GroupeParticipant = get_object_or_404(GroupeParticipant, id=groupe_id)
                inscrire_groupe_a_epreuve(groupe, epreuve)

            messages.success(request, "Les groupes et leurs membres ont été inscrits avec succès à l'épreuve.")
            return redirect('espace_organisateur')
    else:
        # Récupère les groupes non encore inscrits à cette épreuve pour les afficher dans le formulaire.
        groupes_inscrits_ids: List[int] = list(GroupeParticipeAEpreuve.objects.filter(
            epreuve=epreuve).values_list('groupe__id', flat=True))
        groupes_non_inscrits: QuerySet[GroupeParticipant] = (
            GroupeParticipant.objects.filter(referent=request.user, statut="VALIDE").exclude(id__in=groupes_inscrits_ids))

    return render(request, 'epreuve/inscrire_groupes_epreuve.html',
                  {'epreuve': epreuve, 'groupes': groupes_non_inscrits})


@login_required
@decorators.administrateur_exercice_required
def supprimer_exercice(request: HttpRequest, id_exercice: int) -> HttpResponse:
    """
    Supprime un exercice spécifique et affiche un message de succès.

    Cette vue est accessible uniquement aux utilisateurs qui ont les droits nécessaires sur
    l'exercice, vérifiés par le décorateur 'administrateur_exercice_required'. L'exercice à supprimer
    est identifié par son ID et est récupéré automatiquement par le décorateur.

    Args:
        request (HttpRequest): L'objet HttpRequest.
        id_exercice (int): L'identifiant de l'exercice à supprimer.

    Returns:
        HttpResponse: Redirige vers l'espace organisateur après la suppression de l'exercice.
    """
    # L'objet exercice est récupéré par le décorateur 'administrateur_exercice_required'
    exercice: Exercice = getattr(request, 'exercice', None)

    # Sauvegarde le titre et le nom de l'épreuve avant la suppression pour l'utiliser dans le message
    titre_exercice: str = exercice.titre
    nom_epreuve: str = exercice.epreuve.nom

    # Procède à la suppression de l'exercice
    exercice.delete()

    # Affiche un message de succès incluant le titre de l'exercice et le nom de l'épreuve
    messages.success(request, f"L'exercice '{titre_exercice}' de l'épreuve '{nom_epreuve}' a été supprimé.")

    # Redirige vers l'espace organisateur après la suppression
    return redirect('espace_organisateur')


@login_required
@decorators.administrateur_exercice_required
def redistribuer_jeux_de_test(request: HttpRequest, id_exercice: int) -> HttpResponse:
    # L'objet exercice est récupéré par le décorateur 'administrateur_exercice_required'
    exercice: Exercice = getattr(request, 'exercice', None)
    # L'objet épreuve est récupéré par le décorateur 'administrateur_exercice_required'
    epreuve: Epreuve = getattr(request, 'epreuve', None)
    if exercice.avec_jeu_de_test:
        redistribuer_jeux_de_test_exercice(exercice)
        # Rediriger l'utilisateur vers la page précédente
        messages.success(request, "Jeux de test redistribués avec succès.")
    else:
        messages.error(request, f"L'exercice {exercice.titre} de l'épreuve {epreuve.nom} "
                                f"n'est pas un exercice avec jeux de test.")
    return redirect('editer_exercice', id_exercice=id_exercice)


@login_required
@decorators.administrateur_exercice_required
def assigner_jeux_de_test(request: HttpRequest, id_exercice: int) -> HttpResponse:
    # L'objet exercice est récupéré par le décorateur 'administrateur_exercice_required'
    exercice: Exercice = getattr(request, 'exercice', None)

    # L'objet épreuve est récupéré par le décorateur 'administrateur_exercice_required'
    epreuve: Epreuve = getattr(request, 'epreuve', None)

    # Trouver les participants sans jeu de test attribué
    if exercice.avec_jeu_de_test:
        participants_sans_jeu = UserExercice.objects.filter(exercice=exercice, jeu_de_test__isnull=True)
        assigner_participants_jeux_de_test(participants_sans_jeu, exercice)
        messages.success(request, "Les jeux de test ont été assignés aux participants qui n'en n'avaient pas.")
    else:
        messages.error(request, f"L'exercice {exercice.titre} de l'épreuve {epreuve.nom} "
                                f"n'est pas un exercice avec jeux de test.")
    return redirect('editer_exercice', id_exercice=id_exercice)


@login_required
@decorators.administrateur_exercice_required
def supprimer_jeux_de_test(request: HttpRequest, id_exercice: int) -> HttpResponse:
    """
    Supprime tous les jeux de test associés à un exercice spécifique.

    Cette vue est protégée par deux décorateurs qui garantissent que l'utilisateur est connecté
    et qu'il a les droits d'administrateur sur l'exercice concerné (soit en étant le référent
    de l'épreuve associée, soit l'auteur de l'exercice).

    Args:
        request (HttpRequest): L'objet HttpRequest.
        id_exercice (int): L'identifiant de l'exercice dont les jeux de test doivent être supprimés.

    Returns:
        HttpResponse: Redirige vers la vue d'édition de l'exercice après la suppression des jeux de test.
    """

    # Récupère tous les jeux de test associés à l'exercice spécifié par son ID
    jdts = JeuDeTest.objects.filter(exercice_id=id_exercice)

    # Parcourt chaque jeu de test et le supprime
    for jdt in jdts:
        jdt.delete()

    # Après la suppression, redirige vers la vue d'édition de l'exercice pour refléter les changements
    return redirect('editer_exercice', id_exercice=id_exercice)


@login_required
@decorators.administrateur_exercice_required
def creer_editer_exercice(request: HttpRequest, epreuve_id: int, id_exercice: Optional[int] = None) -> HttpResponse:
    """
    Vue pour créer ou éditer un exercice dans une épreuve spécifique.

    Cette vue gère à la fois la création d'un nouvel exercice et l'édition d'un exercice existant
    pour une épreuve donnée. Elle vérifie les permissions de l'utilisateur, traite le formulaire
    d'exercice, et gère la logique d'affichage appropriée selon le contexte (création ou édition).

    Args:
        request (HttpRequest): L'objet requête HTTP.
        id_exercice (Union[int, None], optional): L'identifiant de l'exercice à éditer, si applicable. Defaults to None.

    Returns:
        HttpResponse: La réponse HTTP rendue.
    """

    # L'objet épreuve est récupéré par le décorateur 'administrateur_exercice_required'
    epreuve: Epreuve = getattr(request, 'epreuve', None)
    # Initialise le formulaire pour l'édition si un id_exercice est fourni, sinon pour la création
    if id_exercice:
        # L'objet exercice est récupéré par le décorateur 'administrateur_exercice_required'
        exercice: Exercice = getattr(request, 'exercice', None)
        form = ExerciceForm(request.POST or None, instance=exercice)
    else:
        form = ExerciceForm(request.POST or None)

    # Traite le formulaire lors de la soumission
    if request.method == "POST" and form.is_valid():
        exercice = form.save(commit=False)
        exercice.epreuve = epreuve  # Assigne l'épreuve à l'exercice
        exercice.auteur = request.user  # Définit l'utilisateur actuel comme auteur de l'exercice
        exercice.save()  # Sauvegarde l'exercice dans la base de données

        # Gère les jeux de test si le champ 'avec_jeu_de_test' est coché
        if form.cleaned_data.get('avec_jeu_de_test'):
            jeux_de_tests = form.cleaned_data.get('jeux_de_test', '').split("\n")
            resultats_jeux_de_tests = form.cleaned_data.get('resultats_jeux_de_test', '').split("\n")

            # Supprime les anciens jeux de test en cas d'édition
            if id_exercice:
                exercice.jeudetest_set.all().delete()

            # Crée de nouveaux jeux de test
            for jeu, resultat in zip(jeux_de_tests, resultats_jeux_de_tests):
                if jeu.strip() and resultat.strip():
                    JeuDeTest.objects.create(exercice=exercice, instance=jeu, reponse=resultat)

        # Affiche un message de succès et redirige vers l'espace organisateur
        messages.success(request,
                         'L\'exercice a été ajouté avec succès.'
                         if not id_exercice else 'L\'exercice a été mis à jour avec succès.')
        return redirect('espace_organisateur')

    # Prépare les champs du formulaire à afficher, en distinguant les champs visibles des champs initialement cachés
    champs_invisibles = ['jeux_de_test', 'resultats_jeux_de_test', 'retour_en_direct']
    champs_visibles = [field.name for field in form.visible_fields() if field.name not in champs_invisibles]

    # Rend le template avec le formulaire et les informations nécessaires
    return render(request, 'epreuve/creer_exercice.html', {
        'form': form,
        'champs_visibles': champs_visibles,
        'champs_invisibles': champs_invisibles,
        'epreuve': epreuve,
        'exercice_id': id_exercice,  # Pour identifier si c'est une édition
    })
