from django import forms
from epreuve.models import Epreuve


class EpreuveForm(forms.ModelForm):
    class Meta:
        model = Epreuve
        fields = ['nom', 'description', 'date_debut', 'date_fin', 'duree', 'temps_limite',
                  'exercices_un_par_un']

        labels = {
            'nom': "Nom",
            'description': "Description",
            'date_debut': "Date/Heure d'ouverture",
            'date_fin': "Date/Heure de cloture",
            'exercices_un_par_un': "Ordre exercices imposé",
            'duree': "Durée de l'épreuve par candidat (minutes)",
            'temps_limite': "Empêcher la soumission après expiration de la durée"
        }

        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Entrez le nom de l\'épreuve',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Nom de l’épreuve, tel qu’il apparaîtra aux participants.'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Décrivez l\'épreuve',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Description détaillée de l’épreuve.'
            }),
            'date_debut': forms.DateTimeInput(attrs={
                'class': 'form-control datetimepicker-input',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Date et heure de début de l’épreuve.',
                'type': 'datetime-local'
            }),
            'date_fin': forms.DateTimeInput(attrs={
                'class': 'form-control datetimepicker-input',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Date et heure de fin de l’épreuve.',
                'type': 'datetime-local'
            }),
            'duree': forms.NumberInput(attrs={
                'class': 'form-control',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Durée totale accordée à chaque participant pour l’épreuve (en minutes).'
            }),
            'exercices_un_par_un': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Si coché, les participants doivent compléter les exercices dans l’ordre et ne peuvent pas revenir en arrière.'
            }),
            'temps_limite': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Si coché, l\'heure de début de l’épreuve est enregistrée et les participants ne peuvent pas soumettre de réponses après le temps indiqué dans "Durée de l’épreuve".'
            }),
        }
        required_fields = ['nom', 'duree']
        optional_fields = ['description', 'date_debut', 'date_fin']

    def __init__(self, *args, **kwargs):
        super(EpreuveForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            print(field_name, field.required)
            if field.required:
                field.label = f"{field.label} *"

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if date_debut and date_fin and date_fin < date_debut:
            self.add_error('date_fin', 'La date de fin doit être postérieure à la date de début.')

        return cleaned_data
