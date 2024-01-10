from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from epreuve.models import Epreuve, GroupeCreePar, GroupeParticipeAEpreuve
from epreuve.forms import EpreuveForm


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
    # Récupérez l'épreuve à partir de son ID
    epreuve = get_object_or_404(Epreuve, id=epreuve_id)

    # Logique supplémentaire si nécessaire

    return render(request, 'epreuve/afficher_epreuve.html', {'epreuve': epreuve})
