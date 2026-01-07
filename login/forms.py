from __future__ import annotations

from typing import Any, cast

from captcha.fields import CaptchaField
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from epreuve.models import Epreuve
from olympiadesnsi import settings
from olympiadesnsi.constants import NB_TENTATIVES_CONNEXIONS_AVANT_CAPTCHA, MAX_TAILLE_NOM


class ChampsStripMixin:
    """
    Mixin pour normaliser certains champs de formulaire en supprimant les espaces
    en début et en fin de chaîne.

    Utilisation :
    - déclarer `champs_a_stripper` dans le formulaire
    - les valeurs de ces champs seront automatiquement `strip()` dans `clean()`

    Objectif :
    - éviter les erreurs liées aux copier-coller (espaces invisibles)
    - uniformiser les entrées utilisateur sans dupliquer du code
    """

    champs_a_stripper: tuple[str, ...] = ()

    def clean(self) -> dict[str, Any]:
        donnees: dict[str, Any] = super().clean()

        for nom_champ in self.champs_a_stripper:
            valeur: Any = donnees.get(nom_champ)
            if isinstance(valeur, str):
                donnees[nom_champ] = valeur.strip()

        return donnees


class LoginForm(ChampsStripMixin, forms.Form):
    """
    Formulaire de connexion.

    Notes :
    - le champ `username` est normalisé via `strip()`
    - le captcha est optionnel au départ, puis devient requis si le nombre de tentatives
      échouées stockées en session dépasse un seuil
    - si `settings.CAPTCHA` est False, le champ captcha est retiré du formulaire
    """

    champs_a_stripper: tuple[str, ...] = ("username",)

    username = forms.CharField(
        max_length=MAX_TAILLE_NOM,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Nom d’utilisateur")}),
        error_messages={"required": _("Veuillez entrer votre nom d’utilisateur.")},
        label=_("Nom d’utilisateur"),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": _("Mot de passe")}),
        error_messages={"required": _("Veuillez entrer votre mot de passe.")},
        label=_("Mot de passe"),
    )

    # Champ ajouté par défaut, puis éventuellement retiré si CAPTCHA désactivé.
    captcha = CaptchaField(required=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # La requête est utilisée uniquement pour lire la session (tentatives échouées)
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Désactivation globale du captcha (utile en local/tests)
        if not getattr(settings, "CAPTCHA", True):
            self.fields.pop("captcha", None)
            return

        # Activation conditionnelle du captcha après X tentatives échouées
        if self.request is not None and hasattr(self.request, "session"):
            tentatives: int = int(self.request.session.get("failed_login_attempts", 0))
            if tentatives > NB_TENTATIVES_CONNEXIONS_AVANT_CAPTCHA:
                self.fields["captcha"].required = True
                self.fields["captcha"].widget.attrs.update({"class": "form-control"})
                self.fields["captcha"].error_messages = {"required": _("Veuillez résoudre le captcha.")}

    def clean_username(self) -> str:
        """
        Normalise explicitement le champ `username`.

        Même si le mixin gère déjà le `strip()` au niveau `clean()`, cette méthode
        garantit que `cleaned_data["username"]` est bien une chaîne normalisée et
        évite des surprises si le formulaire évolue.
        """
        username: str = (self.cleaned_data.get("username") or "").strip()
        return username


class PreLoginForm(ChampsStripMixin, forms.Form):
    """
    Formulaire de pré-connexion.

    Objectif :
    - l'utilisateur saisit uniquement son nom d'utilisateur
    - on redirige ensuite vers `set_password` (si pas de mot de passe / inactif) ou
      vers la page de login (si compte actif avec mot de passe)

    Améliorations :
    - `strip()` automatique sur `username` pour éviter les espaces ajoutés par copier-coller
    - message explicite si l'utilisateur n'existe pas
    """

    champs_a_stripper: tuple[str, ...] = ("username",)

    username = forms.CharField(
        label=_("Nom d’utilisateur"),
        max_length=MAX_TAILLE_NOM,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Nom d’utilisateur")}),
        error_messages={"required": _("Veuillez entrer votre nom d’utilisateur.")},
    )

    def clean_username(self) -> str:
        """
        Supprime les espaces superflus et vérifie l'existence du compte.

        Raises:
            ValidationError: si aucun utilisateur ne correspond.
        """
        username: str = (self.cleaned_data.get("username") or "").strip()

        if not User.objects.filter(username=username).exists():
            raise ValidationError(_("Aucun utilisateur trouvé avec ce nom d’utilisateur."))

        return username


class RecoveryForm(ChampsStripMixin, forms.Form):
    """
    Formulaire de récupération de compte.

    Objectif :
    - l'utilisateur renseigne un `username` + l'email du référent (inscripteur externe)
    - un captcha peut être exigé selon `settings.CAPTCHA`

    Améliorations :
    - `strip()` automatique sur `username` et `email`
    - message explicite si le compte n'existe pas (erreur sur le champ `username`)
    """

    champs_a_stripper: tuple[str, ...] = ("username", "email")

    username = forms.CharField(
        label=_("Nom d’utilisateur"),
        max_length=MAX_TAILLE_NOM,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Nom d’utilisateur")}),
        error_messages={
            "required": _("Veuillez entrer le nom d’utilisateur pour lequel vous souhaitez récupérer le compte.")
        },
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": _("E-mail")}),
        error_messages={"required": _("Veuillez entrer votre adresse e-mail.")},
        label=_("E-mail"),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Captcha uniquement si activé dans les settings
        if getattr(settings, "CAPTCHA", True):
            self.fields["captcha"] = CaptchaField(
                required=True,
                error_messages={"required": _("Veuillez résoudre le captcha.")},
            )
            self.fields["captcha"].widget.attrs.update({"class": "form-control"})

    def clean_username(self) -> str:
        """
        Supprime les espaces superflus et vérifie l'existence du compte.

        Raises:
            ValidationError: si aucun utilisateur ne correspond.
        """
        username: str = (self.cleaned_data.get("username") or "").strip()

        if not User.objects.filter(username=username).exists():
            raise ValidationError(
                _("Aucun utilisateur trouvé avec ce nom d’utilisateur. Vérifiez qu’il n’y a pas d’espace en trop.")
            )

        return username

    def clean_email(self) -> str:
        """
        Normalise l'email en supprimant les espaces superflus.
        """
        email: str = (self.cleaned_data.get("email") or "").strip()
        return email


class AjoutOrganisateurForm(forms.Form):
    """
    Formulaire pour ajouter un nouvel organisateur à une épreuve.

    Ce formulaire permet d'ajouter un utilisateur existant au comité d'organisation
    d'une épreuve. Les validations effectuées :
    - l'utilisateur existe,
    - il n'est pas déjà membre du comité,
    - il n'est pas le référent de l'épreuve.
    """

    username: forms.CharField = forms.CharField(
        label="Nom d'utilisateur",
        max_length=100,
        help_text="Nom d'utilisateur de la personne à ajouter au comité.",
    )

    # Attributs supplémentaires passés lors de l'initialisation
    epreuve: Epreuve
    request_user: User

    def __init__(self, *args: tuple[Any, ...], **kwargs: dict[str, Any]) -> None:
        """
        Initialise le formulaire avec des paramètres contextuels.

        Args:
            epreuve (Epreuve): L'épreuve concernée.
            request_user (User): L'utilisateur à l'origine de la demande.
        """
        self.epreuve = cast(Epreuve, kwargs.pop("epreuve"))
        self.request_user = cast(User, kwargs.pop("request_user"))
        super().__init__(*args, **kwargs)

    def clean_username(self) -> str:
        """
        Validation personnalisée du champ `username`.

        Raises:
            ValidationError: si l'utilisateur n'existe pas, est déjà membre du comité
            ou est référent de l'épreuve.

        Returns:
            str: le nom d'utilisateur validé (sans espaces superflus).
        """
        username: str = (self.cleaned_data.get("username") or "").strip()

        # Vérification de l'existence de l'utilisateur
        try:
            user: User = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise ValidationError(_("Aucun utilisateur avec ce nom n'existe.")) from exc

        # L'utilisateur est-il déjà membre du comité ?
        if self.epreuve.a_pour_membre_comite(user):
            raise ValidationError(_("Cet utilisateur fait déjà partie du comité d'organisation."))

        # Est-il déjà référent ?
        if user == self.epreuve.referent:
            raise ValidationError(_("Le référent est déjà responsable de cette épreuve."))

        return username
