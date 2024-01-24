from django.core.serializers import serialize
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.contrib import messages

from epreuve.models import Epreuve, GroupeCreePar, GroupeParticipeAEpreuve, UserExercice, Exercice, UserEpreuve, \
    JeuDeTest
from epreuve.forms import EpreuveForm, ExerciceForm
import json
from datetime import timedelta
import random


@login_required
def inscrire_epreuves(request, id_groupe):
    if request.method == 'POST':
        groupe_cree_par: GroupeCreePar = get_object_or_404(GroupeCreePar, id=id_groupe)
        epreuves_ids = request.POST.getlist('epreuves')

        for epreuve_id in epreuves_ids:
            epreuve = get_object_or_404(Epreuve, id=epreuve_id)

            # Nouvelle inscription en utilisant l'ID du groupe
            _, created = GroupeParticipeAEpreuve.objects.get_or_create(
                groupe_id=groupe_cree_par.groupe_id,
                epreuve=epreuve
            )

        return redirect('espace_organisateur')

    return redirect('gerer_groupe', id_groupe=id_groupe)


@login_required
def gerer_groupe(request, id_groupe):
    groupe_cree_par = get_object_or_404(GroupeCreePar, id=id_groupe)
    nombre_utilisateurs = groupe_cree_par.nombre_participants
    epreuves_inscrites = GroupeParticipeAEpreuve.objects.filter(groupe_id=id_groupe)
    epreuves = Epreuve.objects.all()  # Récupérer toutes les épreuves disponibles

    return render(request, 'epreuve/gerer_groupe.html', {
        'groupe': groupe_cree_par,
        'nombre_utilisateurs': nombre_utilisateurs,
        'epreuves_inscrites': epreuves_inscrites,
        'epreuves': epreuves,
    })


@login_required
def detail_epreuve(request, epreuve_id):
    epreuve = get_object_or_404(Epreuve, id=epreuve_id)
    return render(request, 'epreuve/detail_epreuve.html', {'epreuve': epreuve})


@login_required
def afficher_epreuve(request, epreuve_id):
    epreuve = get_object_or_404(Epreuve, id=epreuve_id)
    user = request.user

    # Récupérer tous les exercices liés à cette épreuve
    exercices = Exercice.objects.filter(epreuve=epreuve)
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
        print("exercice ", ex)
        # Récupérer l'objet UserExercice correspondant
        user_exercice, created = UserExercice.objects.get_or_create(exercice_id=ex.id, participant_id=user.id)
        jeu_de_test = None

        if ex.avec_jeu_de_test and user_exercice.jeu_de_test is not None:
            jeu_de_test = JeuDeTest.objects.get(id=user_exercice.jeu_de_test.id)

        bonne_reponse: str = ""
        instance_de_test: str = ""

        if jeu_de_test is not None:
            print("jeu de test : ", jeu_de_test)
            bonne_reponse = jeu_de_test.reponse
            print("bonen reponse : ", bonne_reponse)
            instance_de_test = jeu_de_test.instance
            print("instance de test : ", instance_de_test)
            print("rep part : ", user_exercice.solution_instance_participant)

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
            'nb_soumissions' : user_exercice.nb_soumissions,
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
        user_epreuve, created = UserEpreuve.objects.get_or_create(
            participant=user,
            epreuve=epreuve,
            defaults={'fin_epreuve': timezone.now() + timedelta(minutes=epreuve.duree)}
        )

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
def assigner_jeu_de_test(request, exercice_id):
    exercice = get_object_or_404(Exercice, pk=exercice_id)
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

    # Rediriger l'utilisateur vers la page précédente
    return redirect('espace_organisateur')


@login_required
def ajouter_exercice(request, epreuve_id):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    epreuve = get_object_or_404(Epreuve, id=epreuve_id)
    if request.method == "POST":
        form = ExerciceForm(request.POST)
        if form.is_valid():
            exercice = form.save(commit=False)
            exercice.epreuve = epreuve
            exercice.save()
            messages.success(request, 'L\'exercice a été ajouté avec succès.')
            return redirect('espace_organisateur')
    else:
        form = ExerciceForm()

    return render(request, 'epreuve/ajouter_exercice.html', {'form': form, 'epreuve': epreuve})


@login_required
def editer_epreuve(request, epreuve_id):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()
    epreuve = get_object_or_404(Epreuve, id=epreuve_id)
    if request.user != epreuve.referent:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = EpreuveForm(request.POST, instance=epreuve)
        if form.is_valid():
            form.save()
            messages.success(request, "L'épreuve a été mise à jour avec succès.")
            return redirect('espace_organisateur')
        else:
            messages.error(request, "Erreur détectée lors de la mise à jour de l'épreuve.")
    else:
        form = EpreuveForm(instance=epreuve)

    return render(request, 'epreuve/editer_epreuve.html', {'form': form, 'epreuve': epreuve})


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

    exercices = Exercice.objects.filter(epreuve=epreuve).prefetch_related('jeu_de_test')

    exercices_json = json.loads(serialize('json', exercices))

    return render(request, 'epreuve/visualiser_epreuve.html', {
        'epreuve': epreuve,
        'exercices_json': json.dumps(exercices_json)
    })

