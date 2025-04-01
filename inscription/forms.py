from typing import cast

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Submit
from django import forms

from epreuve.models import Epreuve
import olympiadesnsi.constants as constantes


class DemandeLienInscriptionForm(forms.Form):
    epreuve = forms.ModelChoiceField(
        queryset=Epreuve.objects.filter(inscription_externe=True),
        label='Épreuve',
        empty_label="Sélectionnez une épreuve",
    )
    identifiant = forms.CharField(
        label='Nom d\'utilisateur de l\'email',
        max_length=constantes.MAX_USERNAME_TAILLE,
        help_text='Entrez le nom d\'utilisateur de votre email académique'
    )
    consentement = forms.BooleanField(
        required=True,
        label="J'autorise la sauvegarde de mon adresse email jusqu'à deux mois après la fin de l'épreuve pour "
              "être contacté dans le cadre des Olympiades de NSI."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        epreuve_field = cast(forms.ModelChoiceField, self.fields['epreuve'])
        epreuve_field.label_from_instance = lambda obj: obj.code

    def label_from_instance(self, obj):
        # Utilise le champ `code` de l'objet Epreuve comme label pour le champ de formulaire
        # mais inclut l'ID de manière transparente pour une utilisation interne
        return obj.code


class EquipeInscriptionForm(forms.Form):
    nombre_participants = forms.IntegerField(label="Nombre d'équipes à inscrire", min_value=1)

    def __init__(self, *args, **kwargs):
        self.max_equipes = kwargs.pop('max_equipes', constantes.MAX_USERS_PAR_GROUPE)
        super().__init__(*args, **kwargs)
        self.fields['nombre_participants'].max_value = self.max_equipes
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
             'nombre_participants',
             #   HTML(f"<p class='text-info'>Nombre d'inscriptions encore possibles : {self.max_equipes}</p>"),
             css_class='form-group'
            ),
            Submit('submit', 'Inscrire des équipes', css_class='btn btn-primary')
        )
