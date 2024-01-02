from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.http import HttpResponseForbidden
import random
import string


@login_required
def espace_candidat(request):
    # Ici, vous pouvez ajouter des logiques supplémentaires si nécessaire
    return render(request, 'intranet/espace_candidat.html')

@login_required
def espace_organisateur(request):
    return render(request, 'intranet/espace_organisateur.html')


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

        # Créer le groupe
        groupe, existe_deja = Group.objects.get_or_create(name=nom_groupe)

        # ID du créateur du groupe (l'utilisateur actuellement connecté)
        id_createur = request.user.id

        # Générer les utilisateurs
        for i in range(1, nombre_utilisateurs + 1):
            username = f"part{id_createur}{groupe.id}{i}"
            password = generate_password()
            user = User.objects.create_user(username=username, password=password)
            groupe.user_set.add(user)

        # Gérer la logique de téléchargement CSV ou stockage des mots de passe

    return redirect('espace_organisateur')


@login_required
def espace_organisateur(request):
    # Récupère les groupes associés à l'organisateur
    groupes = Group.objects.filter(user=request.user)
    return render(request, 'intranet/espace_organisateur.html', {'groupes': groupes})


def generate_password():
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))
