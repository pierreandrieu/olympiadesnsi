import csv
import logging
import zipfile
from collections import defaultdict
from io import BytesIO, StringIO
from random import choice

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet, Count, Prefetch, Case, When, IntegerField, Value, Q, F, Max
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
from epreuve.utils import redistribuer_jeux_de_test_exercice, temps_restant_seconde, vider_jeux_test_exercice
from inscription.utils import assigner_participants_jeux_de_test, inscrire_groupe_a_epreuve
from inscription.models import GroupeParticipeAEpreuve, GroupeParticipant
import olympiadesnsi.decorators as decorators
import json
from typing import List, Optional, Dict, Set, Tuple


logger = logging.getLogger(__name__)


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

    if epreuve.pas_commencee():
        return render(request, 'epreuve/erreurs/epreuve_pas_encore_ouverte.html')

    if epreuve.est_close():
        return render(request, 'epreuve/erreurs/epreuve_terminee.html')

    # Calcul du temps restant pour compléter l'épreuve, si applicable.
    temps_restant: Optional[int] = None
    if epreuve and epreuve.temps_limite:
        user_epreuve, _ = UserEpreuve.objects.get_or_create(participant=user, epreuve=epreuve)
        if not user_epreuve.debut_epreuve:
            # Convertit la durée de l'épreuve en minutes en un objet timedelta
            user_epreuve.debut_epreuve = timezone.now()
            user_epreuve.save()

        # Calcul du temps restant
        temps_restant = temps_restant_seconde(user_epreuve, epreuve)
        if temps_restant < 1:
            return render(request, 'epreuve/erreurs/temps_ecoule.html')

    # Sélection de tous les exercices associés à l'épreuve, ordonnés par leur numéro.
    exercices: List[Exercice] = list(Exercice.objects.filter(epreuve=epreuve).order_by('numero'))
    exercice_a_traiter_si_un_par_un: Optional[Exercice] = None
    for exercice in exercices:
        user_exercice, _ = UserExercice.objects.get_or_create(exercice=exercice, participant=user)
        if not user_exercice.solution_instance_participant or not user_exercice.code_participant:
            exercice_a_traiter_si_un_par_un = exercice
        if exercice.avec_jeu_de_test and not user_exercice.jeu_de_test:
            user_exercice.jeu_de_test = exercice.pick_jeu_de_test()

    # Si l'épreuve impose de passer les exercices un par un, filtrer pour ne garder que le premier non complété.
    if epreuve and epreuve.exercices_un_par_un:
        exercices = [exercice_a_traiter_si_un_par_un]

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
            'reponse_jeu_de_test_enregistree': user_exercice.solution_instance_participant,
            'code_enregistre': user_exercice.code_participant,
            'code_a_soumettre': ex.code_a_soumettre,
            'nb_soumissions_restantes': ex.nombre_max_soumissions - user_exercice.nb_soumissions,
            'nb_max_soumissions': ex.nombre_max_soumissions,
            'retour_en_direct': ex.retour_en_direct,
            'instance_de_test': jeu_de_test.instance if jeu_de_test else "",
            'reponse_valide': str(user_exercice.solution_instance_participant).split() == (
                str(jeu_de_test.reponse).split() if jeu_de_test else "")
        }

        exercices_json_list.append(exercice_dict)

    # Conversion des données des exercices en JSON pour utilisation côté client.
    exercices_json: str = json.dumps(exercices_json_list)
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
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=405)
    try:
        data = json.loads(request.body)
        exercice_id = data.get('exercice_id')
        code_soumis = data.get('code_soumis', "")
        solution_instance = data.get('solution_instance', "")

        #  Exercice et le jeu de test associé
        try:
            exercice = Exercice.objects.get(id=exercice_id)
        except Exercice.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Exercice introuvable'}, status=404)

        # Epreuve
        epreuve: Epreuve = Epreuve.objects.get(id=exercice.epreuve.id)

        if epreuve.pas_commencee() or epreuve.est_close():
            # Redirige vers 'afficher_epreuve' avec l'argument 'epreuve_id' requis
            return redirect(reverse('afficher_epreuve', kwargs={'epreuve_id': epreuve.id}))

        temps_restant: Optional[int] = None
        if epreuve and epreuve.temps_limite:
            # Association UserEpreuve
            user_epreuve: UserEpreuve = UserEpreuve.objects.get(
                participant=request.user,
                epreuve=epreuve
            )
            if not user_epreuve.debut_epreuve:
                # Convertit la durée de l'épreuve en minutes en un objet timedelta
                user_epreuve.debut_epreuve = timezone.now()
                user_epreuve.save()

            # Calcul du temps restant
            temps_restant = temps_restant_seconde(user_epreuve, epreuve)
            if temps_restant < 1:
                return redirect(reverse('afficher_epreuve', kwargs={'epreuve_id': epreuve.id}))

        # Association UserExercice
        user_exercice = UserExercice.objects.get(
            participant=request.user,
            exercice=exercice
        )

        jeu_de_test = user_exercice.jeu_de_test

        if user_exercice.nb_soumissions >= exercice.nombre_max_soumissions:
            return JsonResponse({'success': False, 'error': 'Nombre maximum de soumissions atteint'}, status=403)

        # Mise à jour des champs
        user_exercice.code_participant = code_soumis
        user_exercice.solution_instance_participant = solution_instance
        user_exercice.nb_soumissions += 1
        user_exercice.save()

        if not exercice.avec_jeu_de_test:
            return JsonResponse({
                'success': True,
                'nb_soumissions_restantes': exercice.nombre_max_soumissions - user_exercice.nb_soumissions,
                'code_enregistre': user_exercice.code_participant,
                'reponse_jeu_de_test_enregistree': user_exercice.solution_instance_participant
            })

        # Vérification de la solution

        reponse_valide: bool = False
        if jeu_de_test and str(solution_instance).strip() == str(jeu_de_test.reponse).strip():
            reponse_valide = True

        return JsonResponse({
            'success': True,
            'reponse_valide': reponse_valide,
            'nb_soumissions_restantes': exercice.nombre_max_soumissions - user_exercice.nb_soumissions,
            'code_enregistre': user_exercice.code_participant,
            'reponse_jeu_de_test_enregistree': user_exercice.solution_instance_participant
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Données invalides'}, status=400)


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
    # Calcul du temps restant pour compléter l'épreuve, si applicable.
    temps_restant_secondes: Optional[int] = None
    if epreuve and epreuve.temps_limite:
        temps_restant_secondes = epreuve.duree * 60

    # Sélection de tous les exercices associés à l'épreuve, ordonnés par leur numéro.
    exercices: List[Exercice] = list(Exercice.objects.filter(epreuve=epreuve).order_by('numero'))

    exercices_json_list: List[Dict[str, object]] = []
    for ex in exercices:
        jeu_de_test: Optional[JeuDeTest] = None
        if ex.avec_jeu_de_test:
            jeu_de_test = choice(JeuDeTest.objects.filter(exercice_id=ex.id))

        exercice_dict: Dict[str, object] = {
            'id': ex.id,
            'titre': ex.titre,
            'bareme': ex.bareme,
            'enonce': ex.enonce,
            'enonce_code': ex.enonce_code,
            'type_exercice': ex.type_exercice,
            'avec_jeu_de_test': ex.avec_jeu_de_test,
            'reponse_jeu_de_test_enregistree': "reponse_eleve",
            'code_enregistre': "code_eleve",
            'code_a_soumettre': ex.code_a_soumettre,
            'nb_soumissions_restantes': ex.nombre_max_soumissions,
            'nb_max_soumissions': ex.nombre_max_soumissions,
            'retour_en_direct': ex.retour_en_direct,
            'instance_de_test': jeu_de_test.instance if jeu_de_test else "",
            'reponse_valide': False,
            'reponse_attendue' : jeu_de_test.reponse if jeu_de_test else ""
        }

        exercices_json_list.append(exercice_dict)

    # Conversion des données des exercices en JSON pour utilisation côté client.
    exercices_json: str = json.dumps(exercices_json_list)
    return render(request, 'epreuve/visualiser_epreuve.html', {
        'epreuve': epreuve,
        'exercices_json': exercices_json,
        'temps_restant': temps_restant_secondes
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
@decorators.membre_comite_required
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
    logger.debug("epreuve pour inscription : ", epreuve)

    if request.method == 'POST':
        groupe_ids: List[str] = request.POST.getlist(key='groups', default=[])  # IDs des groupes sélectionnés pour l'inscription.
        logger.debug("id des groupes a inscrire : ", groupe_ids)
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
@decorators.membre_comite_required
def desinscrire_groupe_epreuve(request: HttpRequest, epreuve_id: int, groupe_id: int) -> HttpResponse:
    """
    Désinscrit tous les participants d'un groupe spécifique d'une épreuve donnée.

    Cette fonction supprime toutes les entrées liées dans `UserExercice` pour chaque participant
    et chaque exercice associé à l'épreuve, puis supprime les entrées `UserEpreuve` qui lient
    les participants à l'épreuve.

    Args:
        request (HttpRequest): L'objet requête HTTP.
        groupe_id (int): L'ID du groupe à désinscrire.
        epreuve_id (int): L'ID de l'épreuve de laquelle les participants seront désinscrits.

    Returns:
        HttpResponse: Redirige vers l'espace organisateur avec un message de succès.
    """

    # Récupération de l'épreuve à partir de son ID
    epreuve: Epreuve = get_object_or_404(Epreuve, pk=epreuve_id)
    # Récupération du groupe à désinscrire à partir de son ID
    groupe: GroupeParticipant = get_object_or_404(GroupeParticipant, pk=groupe_id)
    # Récupération de l'association entre groupe et épreuve
    groupe_participe_a_epreuve: GroupeParticipeAEpreuve = get_object_or_404(GroupeParticipeAEpreuve,
                                                                            groupe=groupe,
                                                                            epreuve=epreuve)
    with transaction.atomic():
        participants: QuerySet[User] = groupe.participants()

        # Récupérer tous les UserEpreuve pour l'épreuve et le groupe spécifiés
        user_epreuves = UserEpreuve.objects.filter(epreuve=epreuve, participant__in=participants)

        # Récupérer les IDs de tous les exercices associés à l'épreuve
        exercices_ids: List[int] = list(epreuve.exercices.values_list('id', flat=True))

        # Supprimer tous les UserExercice associés aux participants de l'épreuve et du groupe
        UserExercice.objects.filter(exercice_id__in=exercices_ids,
                                    participant__in=user_epreuves.values_list('participant', flat=True)).delete()

        # Suppression des entrées UserEpreuve pour finaliser la désinscription
        user_epreuves.delete()

        groupe_participe_a_epreuve.delete()

        # Affichage d'un message de succès et redirection
        messages.success(request,
                         f"Les membres du groupe {groupe.nom} ont été désinscrits de l'épreuve {epreuve.nom}.")
        return redirect('espace_organisateur')


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
@decorators.membre_comite_required
def creer_editer_exercice(request: HttpRequest, epreuve_id: int, id_exercice: Optional[int] = None) -> HttpResponse:
    """
    Vue pour créer ou éditer un exercice dans une épreuve spécifique.

    Cette vue gère à la fois la création d'un nouvel exercice et l'édition d'un exercice existant
    pour une épreuve donnée. Elle vérifie les permissions de l'utilisateur, traite le formulaire
    d'exercice, et gère la logique d'affichage appropriée selon le contexte (création ou édition).

    Args:
        request (HttpRequest): L'objet requête HTTP.
        epreuve_id (int): L'identifiant de l'épreuve de l'exercice à éditer
        id_exercice (Union[int, None], optional): L'identifiant de l'exercice à éditer, si applicable. Defaults to None.

    Returns:
        HttpResponse: La réponse HTTP rendue.
    """
    epreuve: Epreuve = getattr(request, 'epreuve', None)
    if id_exercice is None:
        return creer_exercice(request, epreuve)
    else:
        return editer_exercice(request, epreuve, getattr(request, 'exercice', None))


def creer_exercice(request: HttpRequest, epreuve: Epreuve) -> HttpResponse:
    form = ExerciceForm(request.POST or None)
    champs_invisibles = ['jeux_de_test', 'resultats_jeux_de_test', 'retour_en_direct']
    champs_visibles = [field.name for field in form.visible_fields() if field.name not in champs_invisibles]
    if request.method == 'POST':
        if form.is_valid():
            exercice = form.save(commit=False)
            exercice.epreuve = epreuve
            exercice.auteur = request.user
            exercice.save()
            messages.success(request, f"L'exercice {exercice.titre} a été créé avec succès pour l'épreuve {epreuve.nom}.")
            return redirect('espace_organisateur')

    return render(request, 'epreuve/creer_exercice.html', {
        'form': form,
        'champs_visibles': champs_visibles,
        'champs_invisibles': champs_invisibles,
        'epreuve': epreuve,
        'exercice_id': None,
        'separateur_jeux_de_test': "\\n",
        'separateur_resultats_jeux_de_test': "\\n"
    })


def editer_exercice(request: HttpRequest, epreuve: Epreuve, exercice: Exercice) -> HttpResponse:

    jdt_anciens: Set[Tuple[str, str]] = set()
    jeux_de_test: QuerySet[JeuDeTest] = JeuDeTest.objects.filter(exercice=exercice)

    modifications_jdt: bool = False
    # Charger les données existantes des jeux de test si l'exercice les utilise
    jeux_de_test_str, resultats_jeux_de_test_str = "", ""
    if exercice.avec_jeu_de_test:

        jeux_de_test_str = exercice.separateur_jeu_test_effectif.join(jeu.instance for jeu in jeux_de_test)
        resultats_jeux_de_test_str = exercice.separateur_reponse_jeudetest_effectif.join(
            jeu.reponse for jeu in jeux_de_test)

    if request.method == 'POST':
        post_data = request.POST.copy()
        # Remplacer les séparateurs spéciaux par leurs équivalents fonctionnels dans les données POST
        post_data['separateur_jeux_de_test'] = post_data.get('separateur_jeux_de_test').replace('\\n', '\n')
        post_data['separateur_resultats_jeux_de_test'] = post_data.get('separateur_resultats_jeux_de_test').replace('\\n', '\n')

        form = ExerciceForm(post_data, instance=exercice, initial={
            'jeux_de_test': jeux_de_test_str,
            'resultats_jeux_de_test': resultats_jeux_de_test_str,
            'separateur_jeux_de_test': post_data['separateur_jeux_de_test'],
            'separateur_resultats_jeux_de_test':  post_data['separateur_resultats_jeux_de_test'],

        })

        if form.is_valid():
            exercice.separateur_jeu_test = post_data['separateur_jeux_de_test']
            exercice.separateur_reponse_jeudetest = post_data['separateur_resultats_jeux_de_test']
            exercice = form.save()
            # Gère les jeux de test si le champ 'avec_jeu_de_test' est coché
            if form.cleaned_data.get('avec_jeu_de_test'):
                for jeu in jeux_de_test:
                    jdt_anciens.add((jeu.instance, jeu.reponse))
                nouveaux_jdt: Set[Tuple[str, str]] = set()

                jeux_de_tests = form.cleaned_data.get('jeux_de_test', '').split(exercice.separateur_jeu_test_effectif)
                resultats_jeux_de_tests = form.cleaned_data.get(
                    'resultats_jeux_de_test', '').split(exercice.separateur_reponse_jeudetest_effectif)

                # Crée de nouveaux jeux de test
                for jeu, resultat in zip(jeux_de_tests, resultats_jeux_de_tests):
                    nouveaux_jdt.add((jeu, resultat))
                    if jeu.strip() and resultat.strip() and (jeu, resultat) not in jdt_anciens:
                        JeuDeTest.objects.create(exercice=exercice, instance=jeu, reponse=resultat)
                        modifications_jdt = True

                # Supprime les jeux de test qui n'apparaissent plus
                for jeu in jeux_de_test:
                    if (jeu.instance, jeu.reponse) not in nouveaux_jdt:
                        jeu.delete()
                        modifications_jdt = True

                # Redistribue les jeux de test s'il y a une modification
                if modifications_jdt:
                    redistribuer_jeux_de_test_exercice(exercice)

            else:
                vider_jeux_test_exercice(exercice)

            messages.success(request, f"L'exercice {exercice.titre} de l'épreuve {epreuve.nom}"
                                      f" a été mis à jour avec succès.")
            return redirect('espace_organisateur')

    else:
        form = ExerciceForm(instance=exercice, initial={
            'jeux_de_test': jeux_de_test_str,
            'resultats_jeux_de_test': resultats_jeux_de_test_str,
            'separateur_jeux_de_test': exercice.separateur_jeu_test_effectif.replace("\n","\\n"),
            'separateur_resultats_jeux_de_test': exercice.separateur_reponse_jeudetest_effectif.replace("\n", "\\n"),

        })

    champs_invisibles = ['jeux_de_test', 'resultats_jeux_de_test', 'retour_en_direct']
    champs_visibles = [field.name for field in form.visible_fields() if field.name not in champs_invisibles]
    return render(request, 'epreuve/creer_exercice.html', {
        'form': form,
        'champs_visibles': champs_visibles,
        'champs_invisibles': champs_invisibles,
        'jeux_de_test': jeux_de_test_str,
        'resultats_jeux_de_test': resultats_jeux_de_test_str,
        'epreuve': epreuve,
        'exercice_id': exercice.id,
        'separateur_jeux_de_test': exercice.separateur_jeu_test_effectif.replace("\n","\\n"),
        'separateur_resultats_jeux_de_test': exercice.separateur_reponse_jeudetest_effectif.replace("\n", "\\n"),
    })


@login_required
@decorators.membre_comite_required
def rendus_participants(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    epreuve: Epreuve = getattr(request, 'epreuve', None)  # Épreuve récupérée par le décorateur.

    exercices = epreuve.exercices.prefetch_related(
        'jeudetest_set',
        Prefetch('user_exercices', queryset=UserExercice.objects.select_related('participant', 'jeu_de_test'))
    ).all()

    # Récupération des UserExercice avec les informations nécessaires
    user_exercices: QuerySet[UserExercice] = UserExercice.objects.filter(
        exercice__epreuve=epreuve,
        exercice__avec_jeu_de_test=True
    ).select_related('jeu_de_test')

    au_moins_un_exo_avec_jeu_test: bool = False

    # Création d'un dictionnaire pour compter les bonnes réponses pour chaque participant
    bonnes_reponses_par_participant = defaultdict(int)
    for ue in user_exercices:
        if ue.exercice.avec_jeu_de_test:
            au_moins_un_exo_avec_jeu_test = True
            if ue.solution_instance_participant:
                if ue.solution_instance_participant.strip() == ue.jeu_de_test.reponse.strip():
                    bonnes_reponses_par_participant[ue.participant_id] += 1

    # Ajout des informations de bonnes réponses aux participants
    participants: QuerySet[User] = User.objects.filter(
        user_epreuves__epreuve=epreuve
    ).distinct().annotate(
        debut_epreuve=F('user_epreuves__debut_epreuve'),
        groupe_id=Max('appartenances__groupe_id'),
        bonnes_reponses=Case(
            *[When(id=k, then=Value(v)) for k, v in bonnes_reponses_par_participant.items()],
            default=Value(0),
            output_field=IntegerField()
        )
    )

    # Statistiques
    total_inscrits = UserEpreuve.objects.filter(epreuve=epreuve).count()
    total_participants = UserEpreuve.objects.filter(epreuve=epreuve, debut_epreuve__isnull=False).count()

    # Statistiques des groupes (si applicable)
    groupes = GroupeParticipant.objects.filter(epreuves=epreuve)
    total_groupes_inscrits = groupes.count()
    total_groupes_avec_participation: int = groupes.annotate(
        debut_non_null=Count(
            'membres__utilisateur__user_epreuves',
            # Correct si 'user_epreuves' est le related_name dans User pour UserEpreuve
            filter=Q(membres__utilisateur__user_epreuves__debut_epreuve__isnull=False,
                     membres__utilisateur__user_epreuves__epreuve=epreuve)
        )
    ).filter(debut_non_null__gt=0).count()

    data_for_js = [
        {
            'exerciceId': ue.exercice.id,
            'exerciceTitre': ue.exercice.titre,
            'participantId': ue.participant.id,
            'username': ue.participant.username,
            'solution': ue.solution_instance_participant if ue.solution_instance_participant else "N/A",
            'expected': ue.jeu_de_test.reponse if ue.jeu_de_test else "N/A",
            'code': ue.code_participant if ue.code_participant else "N/A",
            'test': ue.jeu_de_test.instance if ue.jeu_de_test else "N/A"
        }
        for ue in user_exercices
    ]
    context = {
        'epreuve': epreuve,
        'exercices': exercices,
        'participants': participants,
        'total_inscrits': total_inscrits,
        'total_participants': total_participants,
        'total_groupes_inscrits': total_groupes_inscrits,
        'au_moins_un_exo_avec_jeu_test': au_moins_un_exo_avec_jeu_test,
        'total_groupes_avec_participation': total_groupes_avec_participation,
        'data_for_js': data_for_js
    }

    return render(request, 'epreuve/rendus_participants.html', context)


@login_required
@decorators.membre_comite_required
def export_data(request, epreuve_id: int, by: str) -> HttpResponse:
    """
    Génère et retourne une archive zip des données des utilisateurs, organisées par exercice ou par participant,
    pour une épreuve donnée.

    Args:
        request (HttpRequest): L'objet HttpRequest.
        epreuve_id (int): ID de l'épreuve pour laquelle les données doivent être exportées.
        by (str): Critère d'organisation de l'exportation ('exercice' ou 'participant').

    Returns:
        HttpResponse: Une réponse HTTP avec l'archive zip en pièce jointe.
    """
    epreuve: Epreuve = getattr(request, 'epreuve', None)  # Épreuve récupérée par le décorateur.

    user_exercices = (UserExercice.objects.filter(exercice__epreuve=epreuve).
                      select_related('exercice', 'participant', 'jeu_de_test'))

    user_epreuves = UserEpreuve.objects.filter(epreuve=epreuve).select_related('participant')

    # Calculer les bonnes réponses
    bonnes_reponses_dict = {}
    for ue in user_exercices:
        # Comparaison en tenant compte de strip()
        is_correct = ue.solution_instance_participant.strip() == ue.jeu_de_test.reponse.strip() if ue.jeu_de_test and ue.solution_instance_participant else False
        bonnes_reponses_dict.setdefault(ue.participant.username, 0)
        if is_correct:
            bonnes_reponses_dict[ue.participant.username] += 1

    # Préparation du fichier CSV
    csv_output = StringIO()
    writer = csv.writer(csv_output)
    writer.writerow(['username', 'date/heure de debut', 'nombre de bonnes reponses'])

    for user_epreuve in UserEpreuve.objects.filter(epreuve=epreuve).select_related('participant'):
        username = user_epreuve.participant.username
        debut = user_epreuve.debut_epreuve.strftime('%Y-%m-%d %H:%M:%S') if user_epreuve.debut_epreuve else 'N/A'
        bonnes_reponses = bonnes_reponses_dict.get(username, 0)
        writer.writerow([username, debut, bonnes_reponses])

    au_moins_un_exo_avec_jeu_test: bool = False

    # Création d'un dictionnaire pour compter les bonnes réponses pour chaque participant
    bonnes_reponses_par_participant = defaultdict(int)
    for ue in user_exercices:
        if ue.exercice.avec_jeu_de_test:
            au_moins_un_exo_avec_jeu_test = True
            if ue.solution_instance_participant:
                if ue.solution_instance_participant.strip() == ue.jeu_de_test.reponse.strip():
                    bonnes_reponses_par_participant[ue.participant_id] += 1

    # Ajout des informations de bonnes réponses aux participants
    participants: QuerySet[User] = User.objects.filter(
        user_epreuves__epreuve=epreuve
    ).distinct().annotate(
        bonnes_reponses=Case(
            *[When(id=k, then=Value(v)) for k, v in bonnes_reponses_par_participant.items()],
            default=Value(0),
            output_field=IntegerField()
        )
    )

    # Création du fichier zip en mémoire
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr('resume_epreuve.csv', csv_output.getvalue())
        if by == 'exercice':
            for exercice in epreuve.exercices.all().prefetch_related('user_exercices'):
                for user_exercice in exercice.user_exercices.all():
                    user = user_exercice.participant
                    user_folder = f"{exercice.titre}/{user.username}"
                    if exercice.avec_jeu_de_test:
                        solution = user_exercice.solution_instance_participant.strip() if user_exercice.solution_instance_participant else ""
                        expected = user_exercice.jeu_de_test.reponse.strip() if user_exercice.jeu_de_test and user_exercice.jeu_de_test.reponse else ""
                        jeu_test_instance: str = "N/A"
                        if user_exercice.jeu_de_test:
                            jeu_test_instance = user_exercice.jeu_de_test.instance
                        zip_file.writestr(f"{user_folder}/jeu_de_test.txt",
                                          f"reponse_partitipant:{solution}\n"
                                          f"reponse_attendue:{expected}\n"
                                          f"jeu_de_test:{jeu_test_instance}")

                    code = user_exercice.code_participant if user_exercice.code_participant else ""
                    zip_file.writestr(f"{user_folder}/code.py", code)
        elif by == 'participant':
            for user in User.objects.filter(user_exercices__exercice__epreuve=epreuve).distinct():
                for user_exercice in user_exercices.filter(participant=user):
                    exercice_folder = f"{user.username}/{user_exercice.exercice.titre}"
                    if user_exercice.exercice.avec_jeu_de_test:
                        solution = user_exercice.solution_instance_participant.strip() if user_exercice.solution_instance_participant else ""
                        expected = user_exercice.jeu_de_test.reponse.strip() if user_exercice.jeu_de_test and user_exercice.jeu_de_test.reponse else ""
                        jeu_test_instance: str = "N/A"
                        if user_exercice.jeu_de_test:
                            jeu_test_instance = user_exercice.jeu_de_test.instance
                        zip_file.writestr(f"{exercice_folder}/jeu_de_test.txt",
                                          f"reponse_partitipant:{solution}\n"
                                          f"reponse_attendue:{expected}\n"
                                          f"jeu_de_test:{jeu_test_instance}")

                    code = user_exercice.code_participant if user_exercice.code_participant else ""
                    zip_file.writestr(f"{exercice_folder}/code.py", code)

    # Réinitialiser le curseur du fichier en mémoire
    zip_buffer.seek(0)

    # Créer la réponse HTTP avec le fichier zip en pièce jointe
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename={by}_data_export_{epreuve_id}.zip'
    return response
