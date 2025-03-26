from typing import cast

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from captcha.fields import CaptchaField

from epreuve.models import Epreuve
from olympiadesnsi.constants import NB_TENTATIVES_CONNEXIONS_AVANT_CAPTCHA, MAX_TAILLE_NOM


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=MAX_TAILLE_NOM,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Nom d’utilisateur')}),
        error_messages={'required': _('Veuillez entrer votre nom d’utilisateur.')},
        label=_('Nom d’utilisateur'),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': _('Mot de passe')}),
        error_messages={'required': _('Veuillez entrer votre mot de passe.')},
        label=_('Mot de passe')
    )
    captcha = CaptchaField(required=False)

    def __init__(self, *args, **kwargs):
        # Récupération de la requête pour accéder à la session
        self.request = kwargs.pop('request', None)
        super(LoginForm, self).__init__(*args, **kwargs)

        # Ajustement conditionnel des champs
        if self.request and hasattr(self.request, 'session'):
            if self.request.session.get('failed_login_attempts', 0) > NB_TENTATIVES_CONNEXIONS_AVANT_CAPTCHA:
                self.fields['captcha'].required = True
                self.fields['captcha'].widget.attrs.update({'class': 'form-control'})
                self.fields['captcha'].error_messages = {'required': _('Veuillez résoudre le captcha.')}


class PreLoginForm(forms.Form):
    username = forms.CharField(label='Nom d’utilisateur', max_length=MAX_TAILLE_NOM)


class RecoveryForm(forms.Form):
    username = forms.CharField(
        label='Nom d’utilisateur',
        max_length=MAX_TAILLE_NOM,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Nom d’utilisateur')}),
        error_messages={
            'required': _('Veuillez entrer le nom d’utilisateur pour lequel vous souhaitez récupérer le compte.')},
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('E-mail')}),
        error_messages={'required': _('Veuillez entrer votre adresse e-mail.')},
        label=_('E-mail')
    )
    captcha = CaptchaField(
        required=True,
        error_messages={'required': _('Veuillez résoudre le captcha.')},
    )


class AjoutOrganisateurForm(forms.Form):
    """
    Formulaire pour ajouter un nouvel organisateur à une épreuve.

    Ce formulaire permet à un administrateur d'épreuve d'ajouter un utilisateur
    existant en tant que membre du comité d'organisation. Il effectue les validations
    suivantes :
    - l'utilisateur existe,
    - il n'est pas déjà membre du comité,
    - il n'est pas le référent de l'épreuve.
    """

    username: forms.CharField = forms.CharField(
        label="Nom d'utilisateur",
        max_length=100,
        help_text="Nom d'utilisateur de la personne à ajouter au comité."
    )

    # Attributs supplémentaires passés lors de l'initialisation
    epreuve: Epreuve
    request_user: User

    def __init__(self, *args: tuple, **kwargs: dict) -> None:
        """
        Initialise le formulaire avec des paramètres contextuels.

        Args:
            epreuve (Epreuve): L'épreuve pour laquelle on souhaite ajouter un organisateur.
            request_user (User): L'utilisateur actuellement connecté (admin de l'épreuve).
        """
        self.epreuve = cast(Epreuve, kwargs.pop("epreuve"))
        self.request_user = cast(User, kwargs.pop("request_user"))
        super().__init__(*args, **kwargs)

    def clean_username(self) -> str:
        """
        Validation personnalisée du champ `username`.

        Vérifie que :
        - l'utilisateur existe,
        - il n'est pas déjà membre du comité d'organisation de l'épreuve,
        - il n'est pas le référent de l’épreuve.

        Raises:
            ValidationError: Si l’une des conditions ci-dessus échoue.

        Returns:
            str: Le nom d'utilisateur validé.
        """
        username: str = self.cleaned_data['username']

        # Vérification de l'existence de l'utilisateur
        try:
            user: User = User.objects.get(username=username)
        except User.DoesNotExist:
            raise ValidationError("Aucun utilisateur avec ce nom n'existe.")

        # L'utilisateur est-il déjà membre du comité ?
        if self.epreuve.a_pour_membre_comite(user):
            raise ValidationError("Cet utilisateur fait déjà partie du comité d'organisation.")

        # Est-il déjà référent ?
        if user == self.epreuve.referent:
            raise ValidationError("Le référent est déjà responsable de cette épreuve.")

        return username
