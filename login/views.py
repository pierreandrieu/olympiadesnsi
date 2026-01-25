from __future__ import annotations

from typing import Optional

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetConfirmView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django_ratelimit.decorators import ratelimit

from .forms import LoginForm, PreLoginForm


# ---------------------------------------------------------------------
# Connexion classique (mot de passe)
# ---------------------------------------------------------------------

def generic_login(
        request_generic: HttpRequest,
        *,
        nom_groupe_autorise: str,
        nom_url_redirection: str,
        template_formulaire: str,
) -> HttpResponse:
    """
    Gère une page de connexion "classique" (username + mot de passe) pour un type d'utilisateur.

    Règles :
        - On authentifie avec `authenticate()`.
        - On vérifie l'appartenance au groupe `nom_groupe_autorise`.
        - En succès : `login()` puis redirection.
        - En échec : message d'erreur.
        - Si `prelogin` a pré-rempli un username, on le consomme via la session.

    Args:
        request_generic: Requête HTTP.
        nom_groupe_autorise: Nom du groupe Django autorisé (ex: "Participant").
        nom_url_redirection: Nom d'URL Django vers lequel rediriger (ex: "espace_participant").
        template_formulaire: Template HTML du formulaire.

    Returns:
        HttpResponse: Page HTML (GET/POST invalide) ou redirection après succès.
    """

    @ratelimit(key="ip", rate="8/s", method="POST", block=True)
    @ratelimit(key="ip", rate="120/m", method="POST", block=True)
    @ratelimit(key="ip", rate="5000/h", method="POST", block=True)
    @ratelimit(key="ip", rate="5/s", method="GET", block=True)
    @ratelimit(key="ip", rate="200/m", method="GET", block=True)
    @ratelimit(key="ip", rate="5000/h", method="GET", block=True)
    def _process(request: HttpRequest) -> HttpResponse:
        username_pre_rempli: Optional[str] = request.session.pop("prelogin_username", None)

        if request.method == "POST":
            form: LoginForm = LoginForm(request.POST, request=request)
            if form.is_valid():
                username: str = form.cleaned_data["username"]
                password: str = form.cleaned_data["password"]

                utilisateur: Optional[User] = authenticate(request, username=username, password=password)

                if utilisateur is not None and utilisateur.groups.filter(name=nom_groupe_autorise).exists():
                    login(request, utilisateur)
                    request.session["failed_login_attempts"] = 0
                    return redirect(nom_url_redirection)

                request.session["failed_login_attempts"] = int(request.session.get("failed_login_attempts", 0)) + 1
                messages.error(request, "Identifiant ou mot de passe incorrect.")
        else:
            # GET
            if username_pre_rempli:
                form = LoginForm(initial={"username": username_pre_rempli})
            else:
                form = LoginForm()

        return render(request, template_formulaire, {"form": form})

    return _process(request_generic)


def login_participant(request: HttpRequest) -> HttpResponse:
    """Connexion des participants (groupe Django : 'Participant')."""
    return generic_login(
        request,
        nom_groupe_autorise="Participant",
        nom_url_redirection="espace_participant",
        template_formulaire="login/login_participant.html",
    )


def login_organisateur(request: HttpRequest) -> HttpResponse:
    """Connexion des organisateurs (groupe Django : 'Organisateur')."""
    return generic_login(
        request,
        nom_groupe_autorise="Organisateur",
        nom_url_redirection="espace_organisateur",
        template_formulaire="login/login_organisateur.html",
    )


def custom_logout(request: HttpRequest) -> HttpResponse:
    """Déconnecte l'utilisateur courant puis redirige vers l'accueil."""
    logout(request)
    return redirect("home")


# ---------------------------------------------------------------------
# Pré-login : si pas de mot de passe, on force le choix d'un mot de passe
# ---------------------------------------------------------------------

@ratelimit(key="ip", rate="8/s", method="POST", block=True)
@ratelimit(key="ip", rate="120/m", method="POST", block=True)
@ratelimit(key="ip", rate="5000/h", method="POST", block=True)
@ratelimit(key="ip", rate="5/s", method="GET", block=True)
@ratelimit(key="ip", rate="200/m", method="GET", block=True)
@ratelimit(key="ip", rate="5000/h", method="GET", block=True)
def prelogin(request: HttpRequest) -> HttpResponse:
    """
    Étape 1 de connexion "élève" :
    - l'élève saisit seulement son username ;
    - si le compte n'a pas de mot de passe utilisable (ou est inactif), on l'envoie vers `set_password` ;
    - sinon, on redirige vers la page de login classique en pré-remplissant le username.

    Important :
        - On utilise `has_usable_password()` (Django standard).
        - Le reset côté prof mettra `set_unusable_password()`, ce qui déclenche ce flux.

    Returns:
        HttpResponse: Formulaire (GET/POST invalide) ou redirection.
    """
    form: PreLoginForm = PreLoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        username: str = form.cleaned_data["username"]

        try:
            utilisateur: User = User.objects.get(username=username)
        except User.DoesNotExist:
            form.add_error(None, "Aucun utilisateur trouvé avec ce nom d’utilisateur.")
            return render(request, "login/prelogin.html", {"form": form})

        if (not utilisateur.is_active) or (not utilisateur.has_usable_password()):
            return redirect("set_password", username=username)

        request.session["prelogin_username"] = username
        return redirect("login_participant")

    return render(request, "login/prelogin.html", {"form": form})


# ---------------------------------------------------------------------
# Choix initial (ou forcé) du mot de passe
# ---------------------------------------------------------------------

@ratelimit(key="ip", rate="8/s", method="POST", block=True)
@ratelimit(key="ip", rate="120/m", method="POST", block=True)
@ratelimit(key="ip", rate="5000/h", method="POST", block=True)
@ratelimit(key="ip", rate="5/s", method="GET", block=True)
@ratelimit(key="ip", rate="200/m", method="GET", block=True)
@ratelimit(key="ip", rate="5000/h", method="GET", block=True)
def set_password(request: HttpRequest, username: str) -> HttpResponse:
    """
    Permet à un utilisateur de définir son mot de passe.

    Usage :
        - première connexion (compte sans mot de passe utilisable)
        - après reset par un enseignant (compte basculé en "unusable password")

    Comportement :
        - en succès : enregistre le mot de passe, active le compte si besoin,
          puis redirige vers le login participant en pré-remplissant le username.

    Args:
        request: Requête HTTP.
        username: Username du compte.

    Returns:
        HttpResponse: Page HTML ou redirection après succès.
    """
    utilisateur: User = get_object_or_404(User, username=username)

    if request.method == "POST":
        form: SetPasswordForm = SetPasswordForm(user=utilisateur, data=request.POST)
        if form.is_valid():
            form.save()

            if not utilisateur.is_active:
                utilisateur.is_active = True
                utilisateur.save(update_fields=["is_active"])

            messages.success(
                request,
                "Votre mot de passe a été défini avec succès. Vous pouvez maintenant vous connecter.",
            )
            request.session["prelogin_username"] = utilisateur.username
            return redirect(reverse("login_participant"))
    else:
        form = SetPasswordForm(user=utilisateur)

    return render(request, "login/set_password.html", {"form": form, "username": username})


def confirmation_modification_mot_de_passe(request: HttpRequest) -> HttpResponse:
    """Page de confirmation après modification du mot de passe (si tu l'utilises encore)."""
    return render(request, "login/confirmation_modification_mot_de_passe.html")


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """
    Si tu utilises encore le flux Django 'password reset' standard ailleurs,
    tu peux conserver ce CBV.
    """
    template_name = "login/custom_password_reset_confirm.html"
    success_url = reverse_lazy("reset_password_done")
