from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from epreuve.models import Epreuve, GroupeCreePar, GroupeParticipeAEpreuve, Exercice, UserEpreuve
from epreuve.forms import EpreuveForm
import json
from django.utils import timezone
from datetime import timedelta


@login_required
def gerer_epreuve(request, epreuve_id):
    epreuve = get_object_or_404(Epreuve, id=epreuve_id, referent=request.user)
    form = EpreuveForm(request.POST or None, instance=epreuve)

    if request.method == 'POST' and form.is_valid():
        form.save()
        # Logique pour gérer les ajouts/suppressions de MaTemplateDoesNotExist at /epreuve/organisateur/epreuve/3/gerernyToMany
        return redirect('espace_organisateur')

    return render(request, 'epreuve/gerer_epreuve.html', {
        'form': form,
        'epreuve': epreuve,
        'epreuve_id': epreuve_id,
    })


@login_required
def inscrire_epreuves(request, id_groupe):
    if request.method == 'POST':
        groupe_cree_par = get_object_or_404(GroupeCreePar, id=id_groupe)
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

    # Récupérer tous les exercices liés à cette épreuve
    exercices = Exercice.objects.filter(epreuve=epreuve)
    # Préparer les données des exercices pour le JavaScript
    # Convertir les exercices en un format JSON pour le frontend
    exercices_json = json.dumps([{
        'id': ex.id,
        'titre': ex.titre,
        'description': ex.description,
        'type_exercice': ex.type_exercice,
        'type_enonce': ex.type_enonce,
        'enonce': ex.enonce,
        'code_a_soumettre': ex.code_a_soumettre,
        'instance_probleme_prog_a_resoudre': ex.instance_probleme_prog_a_resoudre,
    } for ex in exercices])

    temps_restant = None

    if epreuve.duree and epreuve.temps_limite:
        # Préparer les informations de temps pour le frontend
        user = request.user
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
def traiter_reponse_instance(request, exercise_id):
    if request.method == 'POST':
        # ... Traitement ...
        is_correct = True  # Vérifier si la réponse est correcte
        message = "Réponse correcte !" if is_correct else "Réponse incorrecte."

        return JsonResponse({'isSuccess': is_correct, 'message': message})

    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@login_required
def traiter_reponse_code(request, exercice_id):
    if request.method == 'POST':
        # Récupérer les données du POST
        data = json.loads(request.body)
        code = data.get('code')

        # TODO Ajouter la logique pour traiter le code soumis
        # ...

        return JsonResponse({'message': 'Code reçu et traité'})
    else:
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@login_required
def etat_exercices(request, epreuve_id):
    user = request.user
    # Logique pour déterminer l'état des exercices pour cet utilisateur
    etat = {
        # Exemple:
        # 1: 'correct',
        # 2: 'incorrect',
        # 3: 'non_tente'
    }
    return JsonResponse(etat)
