from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import LoginForm
from django_ratelimit.decorators import ratelimit


def generic_login(request: HttpRequest, user_group: str, redirect_url: str, form_template: str) -> HttpResponse:
    """
    Gère la connexion des utilisateurs en fonction de leur groupe. Si les identifiants sont corrects
    et appartiennent au groupe spécifié, l'utilisateur est connecté et redirigé vers l'URL fournie.

    Args:
        request (HttpRequest): Requête HTTP entrante.
        user_group (str): Groupe d'utilisateurs autorisés à se connecter.
        redirect_url (str): URL de redirection après une connexion réussie.
        form_template (str): Chemin du template pour le formulaire de connexion.

    Returns:
        HttpResponse: Réponse HTTP générée pour la requête.
    """

    @ratelimit(key='ip', rate='3/s', method='POST', block=True)
    @ratelimit(key='ip', rate='120/m', method='POST', block=True)
    @ratelimit(key='ip', rate='5000/h', method='POST', block=True)
    @ratelimit(key='ip', rate='5/s', method='GET', block=True)
    @ratelimit(key='ip', rate='200/m', method='GET', block=True)
    @ratelimit(key='ip', rate='5000/h', method='GET', block=True)
    def process_request(request: HttpRequest) -> HttpResponse:
        """
        Traite la requête de connexion avec un rate limiting. Si la requête est une soumission de formulaire,
        le formulaire est validé. Si les identifiants sont corrects et l'utilisateur appartient au groupe
        spécifié, l'utilisateur est connecté. En cas d'échec, un message d'erreur est affiché et le nombre
        de tentatives échouées est incrémenté dans la session.

        Args:
            request (HttpRequest): Requête HTTP entrante.

        Returns:
            HttpResponse: Réponse HTTP à renvoyer au client.
        """
        # Traitement des requêtes POST (soumission du formulaire de connexion)

        if request.method == 'POST':
            # Initialisation du formulaire avec les données POST et la requête
            form = LoginForm(request.POST, request=request)
            # Vérification de la validité du formulaire
            if form.is_valid():
                # Extraction des données validées du formulaire
                username = form.cleaned_data['username']
                password = form.cleaned_data['password']
                # Tentative d'authentification de l'utilisateur avec les identifiants fournis
                user = authenticate(request, username=username, password=password)

                # Vérification si l'utilisateur existe et appartient au groupe spécifié
                if user is not None and user.groups.filter(name=user_group).exists():
                    # Connexion de l'utilisateur
                    login(request, user)
                    # Réinitialisation du compteur de tentatives échouées
                    request.session['failed_login_attempts'] = 0
                    # Redirection vers l'URL spécifiée
                    return redirect(redirect_url)
                else:
                    # En cas d'échec, incrémentation du compteur de tentatives échouées dans la session
                    request.session['failed_login_attempts'] = request.session.get('failed_login_attempts', 0) + 1
                    # Affichage d'un message d'erreur
                    messages.error(request, 'Identifiant ou mot de passe incorrect.')
        else:
            # Pour les requêtes non POST (typiquement GET), initialisation d'un formulaire vierge
            form = LoginForm(request=request)

        # Rendu du template avec le formulaire, pour GET ou POST invalide
        return render(request, form_template, {'form': form})

    # Appel de la fonction interne pour traiter la requête
    return process_request(request)


def login_participant(request: HttpRequest) -> HttpResponse:
    """
    Vue de connexion pour les participants.

    Args:
        request (HttpRequest): La requête HTTP entrante.

    Returns:
        HttpResponse: La réponse HTTP à renvoyer au client.
    """
    return generic_login(
        request,
        user_group='Participant',
        redirect_url='espace_participant',
        form_template='login/login_participant.html'
    )


def login_organisateur(request: HttpRequest) -> HttpResponse:
    """
    Vue de connexion pour les organisateurs.

    Args:
        request (HttpRequest): La requête HTTP entrante.

    Returns:
        HttpResponse: La réponse HTTP à renvoyer au client.
    """
    return generic_login(
        request,
        user_group='Organisateur',
        redirect_url='espace_organisateur',
        form_template='login/login_organisateur.html'
    )


def custom_logout(request: HttpRequest) -> HttpResponse:
    """
    Vue de déconnexion pour les utilisateurs, participants ou organisateurs.

    Args:
        request (HttpRequest): La requête HTTP entrante.

    Returns:
        HttpResponse: La réponse HTTP à renvoyer au client.
    """
    logout(request)
    return redirect('home')
