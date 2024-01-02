from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages


def login_participant(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None and not user.groups.filter(name='Organisateur').exists():
            login(request, user)
            return redirect('espace_candidat')
        else:
            messages.error(request, 'Identifiant ou mot de passe incorrect.')

    return render(request, 'login/login_participant.html')


def login_organisateur(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None and user.groups.filter(name='Organisateur').exists():
            login(request, user)
            return redirect('espace_organisateur')
        else:
            messages.error(request, 'Identifiant ou mot de passe incorrect.')
            return render(request, 'login/login_organisateur.html', {'error': 'Identifiants invalides'})

    # Pour une requête GET, on affiche simplement le formulaire de connexion
    return render(request, 'login/login_organisateur.html')
