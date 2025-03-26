from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetConfirmView
from django.core.mail import EmailMessage
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from inscription.models import InscriptionExterne
from intranet.models import ParticipantEstDansGroupe
from olympiadesnsi import settings
from .forms import LoginForm, PreLoginForm, RecoveryForm
from django_ratelimit.decorators import ratelimit


def generic_login(request_generic: HttpRequest, user_group: str, redirect_url: str, form_template: str) -> HttpResponse:
    """
    Gère la connexion des utilisateurs en fonction de leur groupe. Si les identifiants sont corrects
    et appartiennent au groupe spécifié, l'utilisateur est connecté et redirigé vers l'URL fournie.

    Args:
        request_generic (HttpRequest): Requête HTTP entrante.
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

        prelogin_username = request.session.pop('prelogin_username', None)
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
                    request.session['failed_login_attempts'] = request.session.get(
                        'failed_login_attempts', 0) + 1
                    # Affichage d'un message d'erreur
                    messages.error(request, 'Identifiant ou mot de passe incorrect.')
        else:
            if prelogin_username:
                form: LoginForm = LoginForm(initial={'username': prelogin_username})
            else:
                form: LoginForm = LoginForm()

        # Rendu du template avec le formulaire, pour GET ou POST invalide
        return render(request, form_template, {'form': form})

    # Appel de la fonction interne pour traiter la requête
    return process_request(request_generic)


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


def prelogin(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form: PreLoginForm = PreLoginForm(request.POST)
        if form.is_valid():
            username: str = form.cleaned_data['username']
            try:
                user: User = User.objects.get(username=username)
                if user.password == '' or not user.is_active:
                    # Rediriger vers la page de choix de mot de passe si l'utilisateur n'a pas de mot de passe
                    return redirect('set_password', username=username)
                else:
                    # Rediriger vers la page de connexion normale avec le nom d'utilisateur prérempli
                    request.session['prelogin_username'] = username
                    return redirect('login_participant')
            except User.DoesNotExist:
                # Gestion de l'erreur si l'utilisateur n'existe pas
                form.add_error(None, 'Aucun utilisateur trouvé avec ce nom d’utilisateur.')
    else:
        form: PreLoginForm = PreLoginForm()

    return render(request, 'login/prelogin.html', {'form': form})


def set_password(request: HttpRequest, username: str) -> HttpResponse:
    """
    Permet à un utilisateur de définir son mot de passe.

    Cette vue est destinée aux utilisateurs qui n'ont pas encore de mot de passe défini.
    Elle récupère l'utilisateur par son nom d'utilisateur et présente un formulaire pour
    définir un nouveau mot de passe. Si l'utilisateur a déjà un mot de passe, il est redirigé
    vers la page de connexion.

    Args:
        request (HttpRequest): L'objet requête HTTP.
        username (str): Le nom d'utilisateur pour lequel le mot de passe doit être défini.

    Returns:
        HttpResponse: L'objet réponse HTTP renvoyé au client.
    """

    # Récupération de l'utilisateur par son nom d'utilisateur, avec gestion d'erreur 404 si non trouvé
    user = get_object_or_404(User, username=username)

    # Traitement du formulaire en cas de méthode POST
    if request.method == 'POST':
        # Création d'une instance de formulaire avec les données soumises et l'utilisateur concerné
        form = SetPasswordForm(user=user, data=request.POST)

        # Vérification de la validité du formulaire
        if form.is_valid():
            # Enregistrement du nouveau mot de passe pour l'utilisateur
            form.save()
            # Activation de l'utilisateur s'il était inactif
            if not user.is_active:
                user.is_active = True
                user.save()
            # Affichage d'un message de succès et redirection vers la page de connexion
            messages.success(request,
                             'Votre mot de passe a été défini avec succès. Vous pouvez maintenant vous connecter.')
            request.session['prelogin_username'] = user.username
            return redirect(reverse('login_participant'))
    else:
        # Création d'une instance de formulaire vierge si la requête n'est pas POST
        form = SetPasswordForm(user=user)

    # Affichage de la page avec le formulaire si méthode GET ou formulaire invalide
    return render(request, 'login/set_password.html', {'form': form, 'username': username})


def recuperation_compte(request: HttpRequest) -> HttpResponse:
    form: RecoveryForm = RecoveryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data.get('username')
        email = form.cleaned_data.get('email')
        try:
            user = User.objects.get(username=username)
            groupes_participant = ParticipantEstDansGroupe.objects.filter(utilisateur=user)
            if len(groupes_participant) != 1:
                form.add_error(None, "Aucun compte trouvé avec ces informations.")
            else:
                groupe_participant: ParticipantEstDansGroupe = groupes_participant[0]
                inscription_externe: InscriptionExterne = groupe_participant.groupe.inscription_externe
                email_contact = inscription_externe.inscripteur.email
                if email_contact != email:
                    form.add_error(None, "Aucun compte trouvé avec ces informations.")
                else:
                    # Génération du token de réinitialisation
                    token = default_token_generator.make_token(user)
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    # Construction du lien de réinitialisation
                    reset_link = request.build_absolute_uri(
                        reverse('reset_password_confirm', kwargs={'uidb64': uid, 'token': token})
                    )

                    # Préparation de l'email
                    context = {
                        'reset_link': reset_link,
                        'user': user,
                    }
                    subject = f"Réinitialisation du mot de passe pour l'épreuve {inscription_externe.epreuve.nom}"
                    message = render_to_string('login/contenu_mail_recuperation.html', context)
                    email = EmailMessage(
                        subject=subject,
                        body=message,
                        from_email=settings.EMAIL_HOST_USER,
                        to=[email_contact],
                    )
                    email.content_subtype = "html"
                    # Envoi de l'email
                    email.send()
                    return render(request, 'login/confirmation_envoi_lien_reset_password.html')
        except User.DoesNotExist:
            form.add_error(None, "Aucun compte trouvé avec ces informations.")

    return render(request, 'login/recuperation_compte.html', {'form': form})


def confirmation_modification_mot_de_passe(request):
    return render(request, 'login/confirmation_modification_mot_de_passe.html')


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'login/custom_password_reset_confirm.html'
    success_url = reverse_lazy('reset_password_done')
