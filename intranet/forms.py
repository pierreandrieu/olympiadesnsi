from django import forms
from epreuve.models import Epreuve


class EpreuveForm(forms.ModelForm):
    class Meta:
        model = Epreuve
        fields = ['nom', 'description', 'date_debut', 'date_fin', 'duree',
                  'exercices_un_par_un', 'soumissions_max_par_exercices',
                  'temps_limite', 'presence_flag', 'code_a_soumettre']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 100}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'duree': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'exercices_un_par_un': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'soumissions_max_par_exercices': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'temps_limite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'presence_flag': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'code_a_soumettre': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        optional_fields = ['description', 'date_debut', 'date_fin']

    def __init__(self, *args, **kwargs):
        super(EpreuveForm, self).__init__(*args, **kwargs)
        for field in self.Meta.optional_fields:
            self.fields[field].required = False

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if date_debut and date_fin and date_fin < date_debut:
            self.add_error('date_fin', 'La date de fin doit être postérieure à la date de début.')

        return cleaned_data
