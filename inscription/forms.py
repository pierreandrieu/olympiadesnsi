from django import forms

from epreuve.models import Epreuve


class InscriptionEmailForm(forms.Form):
    # Définition initiale des champs
    email_domaine_choices = [
        ('ac-versailles.fr', '@ac-versailles.fr'),
        ('ac-toulouse.fr', '@ac-toulouse.fr'),
    ]

    email = forms.CharField(label='email')
    domaine_academique = forms.ChoiceField(choices=email_domaine_choices, label='Sélectionnez votre domaine académique')
    consentement = forms.BooleanField(
        required=True,
        label="J'autorise la sauvegarde de mon adresse email jusqu'à deux mois après la fin de l'épreuve pour être contacté dans le cadre des Olympiades de NSI."
    )

    # Constructeur pour personnaliser les widgets
    def __init__(self, *args, **kwargs):
        super(InscriptionEmailForm, self).__init__(*args, **kwargs)
        # Mise à jour des attributs du widget après la définition des champs
        self.fields['email'].widget.attrs.update({'class': 'email-input'})


class EquipeInscriptionForm(forms.Form):
    nombre_equipes = forms.IntegerField(label='Nombre d\'équipes à inscrire', min_value=1, max_value=999)


class ChoixEpreuveForm(forms.Form):
    epreuve = forms.ModelChoiceField(queryset=Epreuve.objects.filter(inscription_externe=True),
                                     empty_label="Sélectionnez une épreuve", label="Épreuve")

