from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import logout
from .forms import LoginForm


def login_participant(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None and not user.groups.filter(name='Organisateur').exists():
                login(request, user)
                return redirect('espace_participant')
            else:
                messages.error(request, 'Identifiant ou mot de passe incorrect.')
    else:
        form = LoginForm()

    return render(request, 'login/login_participant.html', {'form': form})


def login_organisateur(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None and user.groups.filter(name='Organisateur').exists():
                login(request, user)
                return redirect('espace_organisateur')
            else:
                messages.error(request, 'Identifiant ou mot de passe incorrect.')
    else:
        form = LoginForm()

    return render(request, 'login/login_organisateur.html', {'form': form})


def custom_logout(request):
    logout(request)
    return redirect('home')
