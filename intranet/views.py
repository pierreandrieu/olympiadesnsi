from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone  # Pour la date actuelle
from epreuve.models import GroupeCreePar, UserCreePar, Epreuve
from .forms import EpreuveForm
import random
import string


@login_required
def espace_candidat(request):
    # Ici, vous pouvez ajouter des logiques supplémentaires si nécessaire
    return render(request, 'intranet/espace_candidat.html')


@login_required
def gestion_groupes(request):
    # Ici, récupérez et passez les informations des groupes à votre template
    return render(request, 'intranet/gestion_groupes.html')


@login_required
def gestion_epreuves(request):
    # Récupérez et passez les informations des épreuves à votre template
    return render(request, 'intranet/gestion_epreuves.html')


@login_required
def gestion_compte(request):
    # Gérez la logique de gestion du compte utilisateur
    return render(request, 'intranet/gestion_compte.html')


@login_required
def creer_groupe(request):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    if request.method == 'POST':
        nom_groupe = request.POST.get('nom_groupe')
        nombre_utilisateurs = int(request.POST.get('nombre_utilisateurs'))

        # Vérifier si le groupe existe déjà
        groupe, created = Group.objects.get_or_create(name=nom_groupe)

        if not created:
            messages.error(request, 'Un groupe du même nom existe déjà.')
            # Rediriger vers la même page avec un indicateur dans l'URL
            return redirect(reverse('espace_organisateur') + '?openModal=true')

        association = GroupeCreePar(
            groupe=groupe,
            createur=request.user,
            date_creation=timezone.now()  # Date et l'heure actuelles
        )
        association.save()

        # Générer les utilisateurs
        for i in range(1, nombre_utilisateurs + 1):
            username = f"part{groupe.id:05d}_{i:03d}"
            password = generate_password()
            nouvel_utilisateur = User.objects.create_user(username=username, password=password)
            groupe.user_set.add(nouvel_utilisateur)

            # Créer une association UserCreePar
            association_utilisateur = UserCreePar(
                utilisateur=nouvel_utilisateur,  # Passer l'instance de User
                createur=request.user,
                date_creation=timezone.now()  # Date et l'heure actuelles
            )
            association_utilisateur.save()

        # Gérer la logique de téléchargement CSV ou stockage des mots de passe

    return redirect('espace_organisateur')


@login_required
def creer_epreuve(request):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = EpreuveForm(request.POST)
        if form.is_valid():
            epreuve = form.save(commit=False)
            epreuve.referent = request.user  # Définir l'utilisateur actuel comme référent

            epreuve.save()
            form.save_m2m()  # Important pour enregistrer les relations ManyToMany

            messages.success(request, "L'épreuve a été créée avec succès.")
            return redirect('espace_organisateur')
        else:
            messages.error(request, "Il y a eu une erreur dans la création de l'épreuve.")
    else:
        form = EpreuveForm()
    return render(request, 'intranet/espace_organisateur.html', {'form': form})


@login_required
def espace_organisateur(request):
    # Récupère les groupes créés par l'utilisateur connecté
    groupes_crees = GroupeCreePar.objects.filter(createur=request.user)
    # Récupère les épreuves dont l'utilisateur est le référent
    epreuves_crees = Epreuve.objects.filter(referent=request.user)
    epreuve_form = EpreuveForm()
    return render(request, 'intranet/espace_organisateur.html', {
        'groupes_crees': groupes_crees, 'form': epreuve_form, 'epreuves_crees': epreuves_crees})


def generate_password():
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(12))

