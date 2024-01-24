from django import forms
from django.core.exceptions import ValidationError

from epreuve.models import Epreuve, Exercice


class EpreuveForm(forms.ModelForm):
    class Meta:
        model = Epreuve
        fields = ['nom', 'date_debut', 'date_fin', 'duree', 'temps_limite',
                  'exercices_un_par_un']

        labels = {
            'nom': "Nom",
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
        optional_fields = ['date_debut', 'date_fin']

    def __init__(self, *args, **kwargs):
        super(EpreuveForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label} *"

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if date_debut and date_fin and date_fin < date_debut:
            self.add_error('date_fin', 'La date de fin doit être postérieure à la date de début.')

        return cleaned_data


class ExerciceForm(forms.ModelForm):
    jeux_de_tests = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control jeux-de-tests',
            'rows': 5,
        }),
        required=False
    )
    resultats_jeux_de_tests = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control resultats-jeux-de-tests',
            'rows': 5,
        }),
        required=False
    )

    class Meta:
        model = Exercice
        fields = ['titre', 'enonce', 'enonce_code', 'avec_jeu_de_test', 'retour_en_direct', 'code_a_soumettre',
                  'nombre_max_soumissions']
        labels = {
            'titre': 'Titre',
            'enonce': 'Énoncé',
            'enonce_code': 'Code de l\'énoncé',
            'avec_jeu_de_test': 'Avec jeu de test',
            'retour_en_direct': 'Retour en direct',
            'code_a_soumettre': 'Code à soumettre',
            'nombre_max_soumissions': 'Nombre maximum de soumissions'
        }
        widgets = {
            'titre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Entrez le titre de l\'exercice'
            }),
            'enonce': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'title': "L'énoncé de l'exercice, version textuelle, format latex supporté. \nFacultatif si le champ suivant est rempli."
            }),
            'enonce_code': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'title': "L'énoncé de l'exercice, version code. \nFacultatif si le champ précédent est rempli."
            }),
            'avec_jeu_de_test': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'title': "Si coché, les participants se verront attribuer un jeu de test."
            }),
            'retour_en_direct': forms.CheckboxInput(attrs={
                'id': 'id_retour_en_direct',
                'class': 'form-check-input',
                'disabled': True,
                'title': "Si coché, les participants sauront au moment de soumettre leur réponse si leur réponse pour le jeu de test est correcte."
            }),
            'code_a_soumettre': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'title': "Si coché, les participants doivent soumettre leur code."
            }),
            'nombre_max_soumissions': forms.NumberInput(attrs={
                'class': 'form-control',
                'value': 50  # Valeur par défaut
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        enonce = cleaned_data.get('enonce')
        enonce_code = cleaned_data.get('enonce_code')
        avec_jeu_de_test = cleaned_data.get('avec_jeu_de_test')
        if not enonce and not enonce_code:
            raise ValidationError('Vous devez fournir un énoncé, qu\'il soit sous forme de texte ou de code.')

        if avec_jeu_de_test:
            jeux_de_tests = cleaned_data.get('jeux_de_tests', '').split("\n")
            resultats_jeux_de_tests = cleaned_data.get('resultats_jeux_de_tests', '').split("\n")

            nb_jeux_test = len([jeu for jeu in jeux_de_tests if jeu.strip()])  # Ignorer les lignes vides
            nb_resultats = len(
                [resultat for resultat in resultats_jeux_de_tests if resultat.strip()])  # Ignorer les lignes vides
            if nb_jeux_test == 0:
                raise ValidationError('Vous avez coché la case jeux de tests et devez donc insérer au moins un jeu de test avec sa réponse.\nD\'autres jeux de tests pourront être ajoutés ultérieurement')
            if nb_resultats != nb_jeux_test:
                raise ValidationError('Le nombre de jeux de tests inséré doit être le même que le nombre de résultats à ces jeux de tests.\nJeux de tests : ' + str(nb_jeux_test) + " et réponses : " + str(nb_resultats))
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super(ExerciceForm, self).__init__(*args, **kwargs)
        self.fields['titre'].required = True
        self.fields['nombre_max_soumissions'].required = True
        self.initial['nombre_max_soumissions'] = 50


class AjoutOrganisateurForm(forms.Form):
    username = forms.CharField(label='Nom d’utilisateur', max_length=100)


