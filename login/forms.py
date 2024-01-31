from django import forms
from django.utils.translation import gettext_lazy as _
from captcha.fields import CaptchaField


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=100,
        error_messages={'required': _('Veuillez entrer votre nom d’utilisateur.')}
    )
    password = forms.CharField(
        widget=forms.PasswordInput,            #print("form 1", form.fields)

        error_messages={'required': _('Veuillez entrer votre mot de passe.')}
    )
    captcha = CaptchaField(required=False)

    def __init__(self, *args, **kwargs):
        # Récupération de la requête pour accéder à la session
        self.request = kwargs.pop('request', None)
        super(LoginForm, self).__init__(*args, **kwargs)

        # Activation conditionnelle du captcha basée sur le nombre de tentatives échouées
        if self.request and hasattr(self.request, 'session'):
            if self.request.session.get('failed_login_attempts', 0) > 3:
                self.fields['captcha'].required = True
                # Message d'erreur personnalisé pour le captcha
                self.fields['captcha'].error_messages = {'required': _('Veuillez résoudre le captcha.')}
