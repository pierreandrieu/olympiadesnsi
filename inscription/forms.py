from django import forms

from epreuve.models import Epreuve
import olympiadesnsi.constants as constantes

class DemandeLienInscriptionForm(forms.Form):
    epreuve = forms.ModelChoiceField(
        queryset=Epreuve.objects.filter(inscription_externe=True),
        label='Épreuve',
        empty_label="Sélectionnez une épreuve",
        to_field_name="code"  # Utilisez `code` comme valeur à soumettre
    )
    identifiant = forms.CharField(
        label='Email',
        max_length=constantes.MAX_USERNAME_TAILLE,
        help_text='Entrez votre email'
    )
    consentement = forms.BooleanField(
        required=True,
        label="J'autorise la sauvegarde de mon adresse email jusqu'à deux mois après la fin de l'épreuve pour "
              "être contacté dans le cadre des Olympiades de NSI."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['epreuve'].label_from_instance = self.label_from_instance

    def label_from_instance(self, obj):
        # Utilise le champ `code` de l'objet Epreuve comme label pour le champ de formulaire
        # mais inclut l'ID de manière transparente pour une utilisation interne
        return obj.code


class EquipeInscriptionForm(forms.Form):
    nombre_equipes = forms.IntegerField(label='Nombre d\'équipes à inscrire', min_value=1,
                                        max_value=constantes.MAX_USERS_PAR_GROUPE)
