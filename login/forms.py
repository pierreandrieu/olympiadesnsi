from django import forms
from django.utils.translation import gettext_lazy as _
from captcha.fields import CaptchaField


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Nom d’utilisateur')}),
        error_messages={'required': _('Veuillez entrer votre nom d’utilisateur.')},
        label=_('Nom d’utilisateur')
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
            if self.request.session.get('failed_login_attempts', 0) > 3:
                self.fields['captcha'].required = True
                self.fields['captcha'].widget.attrs.update({'class': 'form-control'})
                self.fields['captcha'].error_messages = {'required': _('Veuillez résoudre le captcha.')}
