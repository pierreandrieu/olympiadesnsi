from django.contrib.auth.models import Group, User
from django.core.serializers import serialize
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect, HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
from django.urls import reverse
from epreuve.models import Epreuve, UserExercice, Exercice, UserEpreuve, JeuDeTest, MembreComite
from epreuve.forms import ExerciceForm, AjoutOrganisateurForm
from inscription.models import GroupeParticipeAEpreuve
import json
from datetime import timedelta
import random
from typing import Union


@login_required
def detail_epreuve(request, epreuve_id):
    epreuve = get_object_or_404(Epreuve, id=epreuve_id)
    user = request.user

    # Vérifier si l'utilisateur appartient à un groupe qui participe à l'épreuve
    user_groups = user.groups.all()
    groupe_participation = GroupeParticipeAEpreuve.objects.filter(epreuve=epreuve, groupe__in=user_groups).exists()

    if not groupe_participation:
        return HttpResponseForbidden("Vous n'avez pas l'autorisation de voir cette épreuve.")
    return render(request, 'epreuve/detail_epreuve.html', {'epreuve': epreuve})


@login_required
def afficher_epreuve(request, epreuve_id):
    epreuve = get_object_or_404(Epreuve, id=epreuve_id)
    user = request.user

    # Vérifier si l'utilisateur appartient à un groupe qui participe à l'épreuve
    user_groups = user.groups.all()
    groupe_participation = GroupeParticipeAEpreuve.objects.filter(epreuve=epreuve, groupe__in=user_groups).exists()

    if not groupe_participation:
        return HttpResponseForbidden("Vous n'avez pas l'autorisation de voir cette épreuve.")
    # Récupérer tous les exercices liés à cette épreuve
    exercices = Exercice.objects.filter(epreuve=epreuve).order_by('numero')
    # Préparer les données des exercices pour le JavaScript

    if epreuve.exercices_un_par_un:
        # Trouver le premier exercice non soumis ou invalide
        exercices_list = []
        for ex in exercices:
            user_exercice, _ = UserExercice.objects.get_or_create(exercice_id=ex.id, participant_id=user.id)
            if not user_exercice.solution_instance_participant and not user_exercice.code_participant:
                exercices_list = [ex]
                break
        exercices = exercices_list

    exercices_json_list = []
    for ex in exercices:
        # Récupérer l'objet UserExercice correspondant
        user_exercice, created = UserExercice.objects.get_or_create(exercice_id=ex.id, participant_id=user.id)
        jeu_de_test = None
        if ex.avec_jeu_de_test and user_exercice.jeu_de_test is not None:
            jeu_de_test = JeuDeTest.objects.get(id=user_exercice.jeu_de_test.id)
        bonne_reponse: str = ""
        instance_de_test: str = ""

        if jeu_de_test is not None:
            bonne_reponse = jeu_de_test.reponse
            instance_de_test = jeu_de_test.instance
        # Construire le dictionnaire pour cet exercice
        exercice_dict = {
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
            'instance_de_test': instance_de_test,
            'reponse_valide': user_exercice.solution_instance_participant == bonne_reponse
        }

        # Ajouter le dictionnaire à la liste
        exercices_json_list.append(exercice_dict)

    # Convertir la liste en JSON
    exercices_json = json.dumps(exercices_json_list)
    temps_restant = None
    if epreuve.duree and epreuve.temps_limite:
        # Préparer les informations de temps pour le frontend
        # Récupérer ou créer l'objet UserEpreuve
        user_epreuve, created = UserEpreuve.objects.get_or_create(
            participant=user,
            epreuve=epreuve
        )

        # Vérifier si l'épreuve a une durée limitée et si l'heure de fin est NULL
        if epreuve.duree and not user_epreuve.fin_epreuve:
            # Calculer l'heure de fin basée sur la durée de l'épreuve
            user_epreuve.fin_epreuve = timezone.now() + timedelta(minutes=epreuve.duree)
            user_epreuve.save()

        # Préparer les informations de temps pour le frontend
        if epreuve.duree and epreuve.temps_limite:
            temps_restant = user_epreuve.fin_epreuve - timezone.now()
            if temps_restant.total_seconds() < 0:
                temps_restant = timedelta(seconds=0)
    return render(request, 'epreuve/afficher_epreuve.html', {
        'epreuve': epreuve,
        'exercices_json': exercices_json,
        'temps_restant': temps_restant
    })


@login_required
@csrf_protect
@ratelimit(key='user', rate='10/m', block=True)
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
            user_exercice, created = UserExercice.objects.get_or_create(
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
def supprimer_epreuve(request, epreuve_id):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    epreuve = get_object_or_404(Epreuve, id=epreuve_id)

    if request.user != epreuve.referent:
        return HttpResponseForbidden()

    if request.method == "POST":
        epreuve.delete()
        return redirect('espace_organisateur')

    return redirect('espace_organisateur')


@login_required
def visualiser_epreuve_organisateur(request, epreuve_id):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()
    epreuve = get_object_or_404(Epreuve, id=epreuve_id)

    exercices = Exercice.objects.filter(epreuve=epreuve).order_by('numero').prefetch_related('jeudetest_set')
    exercices_json = json.loads(serialize('json', exercices))

    return render(request, 'epreuve/visualiser_epreuve.html', {
        'epreuve': epreuve,
        'exercices_json': json.dumps(exercices_json)
    })


@login_required
def ajouter_organisateur(request, epreuve_id):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()
    epreuve = get_object_or_404(Epreuve, id=epreuve_id)
    if request.user != epreuve.referent:
        return HttpResponseForbidden()
    form = AjoutOrganisateurForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data['username']
        try:
            organisateur_a_ajouter = User.objects.get(username=username)
            if organisateur_a_ajouter.groups.filter(name='Organisateur').exists():
                if organisateur_a_ajouter.username == request.user.username:
                    messages.error(request, "Vous ne pouvez pas vous ajouter vous-même.")
                elif MembreComite.objects.filter(membre_id=organisateur_a_ajouter, epreuve_id=epreuve_id).exists():
                    messages.error(request, f"{organisateur_a_ajouter.username} fait déjà partie du comité "
                                            f"d'organisation de l'épreuve {epreuve.nom}")
                else:
                    MembreComite.objects.create(epreuve=epreuve, membre=organisateur_a_ajouter)
                    messages.success(request, f"{username} a bien été ajouté au comité d'organisation "
                                              f"de l'épreuve {epreuve.nom}")
            else:
                messages.error(request, "L'utilisateur n'a pas les privilèges nécessaires pour devenir membre "
                                        "d'un comité d'organisation.")
        except User.DoesNotExist:
            messages.error(request, f"L'utilisateur {username} est introuvable.")
        return HttpResponseRedirect(reverse('espace_organisateur'))

    return render(request, 'intranet/espace_organisateur.html', {'form': form})


@login_required
def inscrire_groupes_epreuve(request, epreuve_id):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    epreuve = get_object_or_404(Epreuve, id=epreuve_id)
    if epreuve.referent != request.user:
        return HttpResponseForbidden()

    if request.method == 'POST':
        group_ids = request.POST.getlist('groups')
        exercices = Exercice.objects.filter(epreuve=epreuve_id)
        with transaction.atomic():
            groupes = Group.objects.filter(id__in=group_ids).prefetch_related('user_set')
            for groupe in groupes:
                GroupeParticipeAEpreuve.objects.create(groupe=groupe, epreuve=epreuve)

                for user in groupe.user_set.all():
                    _, _ = UserEpreuve.objects.get_or_create(participant=user, epreuve=epreuve)
                    for exercice in exercices:
                        _, _ = UserExercice.objects.get_or_create(exercice_id=exercice.id, participant_id=user.id)
        messages.success(request, "Les groupes et leurs membres ont été inscrits avec succès à l'épreuve.")
        return redirect('espace_organisateur')

    else:
        groupes_inscrits = GroupeParticipeAEpreuve.objects.filter(epreuve=epreuve).values_list('groupe', flat=True)
        groups = Group.objects.filter(
            associations_groupe_createur__createur=request.user).exclude(id__in=groupes_inscrits)
    return render(request, 'epreuve/inscrire_groupes_epreuve.html', {'epreuve': epreuve, 'groups': groups})


@login_required()
def supprimer_exercice(request, id_exercice):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()
    exercice = get_object_or_404(Exercice, id=id_exercice)
    epreuve_exercice = Epreuve.objects.get(id=exercice.epreuve_id)
    if epreuve_exercice.referent != request.user and exercice.auteur != request.user:
        return HttpResponseForbidden()
    exercice.delete()
    messages.success(request, "L'exercice a été supprimé")
    return redirect('espace_organisateur')


@login_required
def redistribuer_jeux_de_test(request, id_exercice):
    exercice = get_object_or_404(Exercice, pk=id_exercice)
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    # Récupérer tous les ID des Jeux de Test pour cet exercice
    jeux_de_test_ids = JeuDeTest.objects.filter(exercice=exercice).values_list('id', flat=True)
    jeux_de_test_list = list(jeux_de_test_ids)
    random.shuffle(jeux_de_test_list)
    # Trouver les participants sans jeu de test attribué
    participants = UserExercice.objects.filter(exercice=exercice)
    cpt = 0
    for user_exercice in participants:
        if cpt == len(jeux_de_test_list):
            cpt = 0
            random.shuffle(jeux_de_test_list)

        jeu_de_test_id = jeux_de_test_list[cpt]
        cpt += 1

        user_exercice.jeu_de_test_id = jeu_de_test_id
        user_exercice.save()
        # Supprimer l'ID attribué du set des jeux non attribués

    # Rediriger l'utilisateur vers la page précédente
    messages.success(request, "Jeux de test redistribués avec succès.")
    return redirect('editer_exercice', id_exercice=id_exercice)


@login_required
def assigner_jeux_de_test(request, id_exercice):
    exercice = get_object_or_404(Exercice, pk=id_exercice)
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    # Récupérer tous les ID des Jeux de Test pour cet exercice
    jeux_de_test_ids = set(JeuDeTest.objects.filter(exercice=exercice).values_list('id', flat=True))
    # Récupérer les ID des Jeux de Test déjà attribués
    jeux_attribues_ids = set(UserExercice.objects.filter(exercice=exercice, jeu_de_test__isnull=False)
                             .values_list('jeu_de_test_id', flat=True))
    # Calculer les jeux de tests non attribués
    jeux_non_attribues = jeux_de_test_ids - jeux_attribues_ids
    jeux_non_attribues_copie = list(jeux_non_attribues)
    random.shuffle(jeux_non_attribues_copie)
    # Trouver les participants sans jeu de test attribué
    participants_sans_jeu = UserExercice.objects.filter(exercice=exercice, jeu_de_test__isnull=True)
    cpt = 0
    fusion: bool = True
    for user_exercice in participants_sans_jeu:
        if cpt == len(jeux_non_attribues_copie):
            cpt = 0
            if fusion:
                for id_jeu_attribue in jeux_attribues_ids:
                    jeux_non_attribues_copie.append(id_jeu_attribue)
                    fusion = False
            random.shuffle(jeux_non_attribues_copie)

        jeu_de_test_id = jeux_non_attribues_copie[cpt]
        cpt += 1

        user_exercice.jeu_de_test_id = jeu_de_test_id
        user_exercice.save()
        # Supprimer l'ID attribué du set des jeux non attribués

    return redirect('editer_exercice', id_exercice=id_exercice)


@login_required
def supprimer_jeux_de_test(request, id_exercice):
    exercice = Exercice.objects.get(pk=id_exercice)
    if not est_admin_exercice(request, exercice):
        return HttpResponseForbidden("Vous n'avez pas les droits pour supprimer les jeux de test pour cet exercice.")
    jdts = JeuDeTest.objects.filter(exercice_id=id_exercice)
    for jdt in jdts:
        jdt.delete()
    return redirect('editer_exercice', id_exercice=id_exercice)


def est_admin_exercice(request, exercice: Exercice) -> bool:
    if not request.user.groups.filter(name='Organisateur').exists():
        return False
    epreuve_exercice = Epreuve.objects.get(id=exercice.epreuve_id)
    if epreuve_exercice.referent == request.user or exercice.auteur == request.user:
        return True
    return False


@login_required
def creer_editer_exercice(request: HttpRequest, epreuve_id: int, id_exercice: Union[int, None] = None) -> HttpResponse:
    """
    Vue pour créer ou éditer un exercice dans une épreuve spécifique.

    Cette vue gère à la fois la création d'un nouvel exercice et l'édition d'un exercice existant
    pour une épreuve donnée. Elle vérifie les permissions de l'utilisateur, traite le formulaire
    d'exercice, et gère la logique d'affichage appropriée selon le contexte (création ou édition).

    Args:
        request (HttpRequest): L'objet requête HTTP.
        epreuve_id (int): L'identifiant de l'épreuve à laquelle l'exercice appartient.
        id_exercice (Union[int, None], optional): L'identifiant de l'exercice à éditer, si applicable. Defaults to None.

    Returns:
        HttpResponse: La réponse HTTP rendue.
    """
    # Vérifie si l'utilisateur appartient au groupe 'Organisateur', sinon retourne une réponse 'Forbidden'
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    # Récupère l'épreuve concernée ou retourne une erreur 404 si non trouvée
    epreuve = get_object_or_404(Epreuve, id=epreuve_id)

    # Initialise le formulaire pour l'édition si un id_exercice est fourni, sinon pour la création
    if id_exercice:
        exercice = get_object_or_404(Exercice, id=id_exercice, epreuve=epreuve)
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
