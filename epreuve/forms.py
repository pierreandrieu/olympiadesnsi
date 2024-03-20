from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from epreuve.models import Epreuve, Exercice, MembreComite
import re

from olympiadesnsi.constants import DEFAULT_MAX_SOUMISSIONS_PAR_EXERCICE, MAX_USERNAME_TAILLE


class EpreuveForm(forms.ModelForm):

    domaines_autorises = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'form-control',
        'rows': 5,
    }), required=False)

    class Meta:
        model = Epreuve
        fields = ['nom', 'date_debut', 'date_fin', 'duree', 'temps_limite',
                  'exercices_un_par_un', 'inscription_externe', 'domaines_autorises']

        labels = {
            'nom': "Nom",
            'date_debut': "Date/Heure d'ouverture",
            'date_fin': "Date/Heure de cloture",
            'exercices_un_par_un': "Ordre exercices imposé",
            'duree': "Durée de l'épreuve par candidat (minutes)",
            'temps_limite': "Empêcher la soumission après expiration de la durée",
            'inscription_externe': "Autoriser des personnes exernes à l'application à inscrire des participants",
            'domaines_autorises': "Domaines autorises des adresses e-mail pour les inscriptions externes"
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
            }, format='%Y-%m-%dT%H:%M'),
            'date_fin': forms.DateTimeInput(attrs={
                'class': 'form-control datetimepicker-input',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Date et heure de fin de l’épreuve.',
                'type': 'datetime-local'
            }, format='%Y-%m-%dT%H:%M'),
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
                'title': 'Si coché, les participants doivent compléter les exercices dans l’ordre et ne peuvent '
                         'pas revenir en arrière.'
            }),
            'temps_limite': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Si coché, l\'heure de début de l’épreuve est enregistrée et les participants ne peuvent '
                         'pas soumettre de réponses après le temps indiqué dans "Durée de l’épreuve".'
            }),
            'inscription_externe': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Si coché, des personnes extérieures à l\'application peuvent inscrire des participants.'
            }),
            'domaines_autorises': forms.TextInput(attrs={
                'class': 'form-control',
                'data-toggle': 'tooltip',
                'data-placement': 'right',
                'title': 'Domaines autorises des adresses e-mail pour les inscriptions externes.'
            }),
        }
        required_fields = ['nom', 'duree', 'date_debut', 'date_fin']
        optional_fields = ['exercices_un_par_un', 'temps_limite', 'inscription_externe', 'domaines_autorises']

    def __init__(self, *args, **kwargs):
        super(EpreuveForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label} *"

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        inscriptions_externes = cleaned_data.get('inscription_externe')
        domaines_autorises = cleaned_data.get('domaines_autorises')

        if date_debut and date_fin and date_fin < date_debut:
            self.add_error('date_fin', 'La date de fin doit être postérieure à la date de début.')

        if inscriptions_externes:
            if not domaines_autorises:
                raise ValidationError("Il faut au moins un nom de domaine valide puisque les inscriptions externes"
                                       "on été autorisées.")
            # Expression régulière pour valider les domaines
            domain_regex = re.compile(r'^@\w+([-.]\w+)*\.\w{2,}$')
            domaines_list = [d.strip() for d in domaines_autorises.split('\n') if d.strip()]

            invalid_domains = [d for d in domaines_list if not domain_regex.match(d)]
            if invalid_domains:
                invalid_domains_str = ", ".join(invalid_domains)
                self.add_error('domaines_autorises', 'Domaines invalides détectés : ' + invalid_domains_str)

        return cleaned_data


class ExerciceForm(forms.ModelForm):
    jeux_de_test = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control jeux-de-tests hiddenjdt',
            'rows': 5,
        }),
        required=False
    )
    resultats_jeux_de_test = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control resultats-jeux-de-tests hiddenjdt',
            'rows': 5,
        }),
        required=False
    )

    class Meta:
        model = Exercice
        fields = ['titre', 'enonce', 'enonce_code', 'code_a_soumettre', 'nombre_max_soumissions',
                  'avec_jeu_de_test', 'retour_en_direct',]
        labels = {
            'titre': 'Titre',
            'enonce': 'Énoncé',
            'enonce_code': 'Code de l\'énoncé',
            'code_a_soumettre': 'Code à soumettre',
            'nombre_max_soumissions': 'Nombre maximum de soumissions',
            'avec_jeu_de_test': 'Avec jeu de test',
            'retour_en_direct': 'Indicateur de réussite',
        }
        widgets = {
            'titre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Entrez le titre de l\'exercice'
            }),
            'enonce': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'title': "L'énoncé de l'exercice, version textuelle, format latex supporté. "
                         "\nFacultatif si le champ suivant est rempli."
            }),
            'enonce_code': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'title': "L'énoncé de l'exercice, version code. \nFacultatif si le champ précédent est rempli."
            }),
            'code_a_soumettre': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'title': "Si coché, les participants doivent soumettre leur code."
            }),
            'nombre_max_soumissions': forms.NumberInput(attrs={
                'class': 'form-control',
                'value': DEFAULT_MAX_SOUMISSIONS_PAR_EXERCICE  # Valeur par défaut
            }),
            'avec_jeu_de_test': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'title': "Si coché, les participants se verront attribuer un jeu de test."
            }),
            'retour_en_direct': forms.CheckboxInput(attrs={
                'id': 'id_retour_en_direct',
                'class': 'form-check-input hiddenjdt',
                'disabled': True,
                'title': "Si coché, les participants sauront au moment de soumettre leur réponse si "
                         "leur réponse pour le jeu de test est correcte."
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        enonce = cleaned_data.get('enonce')
        enonce_code = cleaned_data.get('enonce_code')
        avec_jeu_de_test = cleaned_data.get('avec_jeu_de_test')
        code_a_soumettre = cleaned_data.get('code_a_soumettre')
        nombre_de_soumissions = str(cleaned_data.get('nombre_max_soumissions')).strip()
        # Vérifier la présence de l'énoncé
        if not enonce and not enonce_code:
            raise ValidationError('Vous devez fournir un énoncé, qu\'il soit sous forme de texte ou de code.')

        if not nombre_de_soumissions.isdigit():
            raise ValidationError('Le nombre de soumissions maximal par participant doit être un entier '
                                  'strictement positif')

        nombre_de_soumissions = int(nombre_de_soumissions)
        if nombre_de_soumissions < 1:
            raise ValidationError('Le nombre de soumissions maximal par participant doit être strictement positif')

        # Vérifier la présence des jeux de test si nécessaire
        if avec_jeu_de_test:
            # Obtenir et filtrer les jeux de tests et les résultats
            jeux_de_tests = [jeu.strip() for jeu in cleaned_data.get('jeux_de_test', '').split("\n") if
                             jeu.strip()]
            resultats_jeux_de_tests = [resultat.strip() for resultat in
                                       cleaned_data.get('resultats_jeux_de_test', '').split("\n") if
                                       resultat.strip()]

            nb_jeux_test = len(jeux_de_tests)
            nb_resultats = len(resultats_jeux_de_tests)

            if nb_resultats != nb_jeux_test:
                raise ValidationError(
                    'Le nombre de jeux de test inséré doit être le même que le nombre de résultats à ces jeux de test.')

            if nb_jeux_test == 0:
                if self.instance.pk and self.instance.jeudetest_set.exists():
                    # L'exercice est en cours de modification et a déjà des jeux de test
                    return cleaned_data

                raise ValidationError(
                    'Vous avez coché la case jeux de test et devez donc insérer au moins'
                    ' un jeu de test avec sa réponse.')

        else:
            if not code_a_soumettre:
                raise ValidationError('Pour un exercice de programmation, il faut demander à ce que'
                                      'le code soit soumis ou alors demander à résoudre un jeu de test. '
                                      'Il faut donc cocher "code à soumettre" ou "avec jeu de test" (ou les deux).')

        return cleaned_data

    def __init__(self, *args, **kwargs):
        super(ExerciceForm, self).__init__(*args, **kwargs)
        self.fields['titre'].required = True
        self.fields['nombre_max_soumissions'].required = True
        self.initial['nombre_max_soumissions'] = DEFAULT_MAX_SOUMISSIONS_PAR_EXERCICE

        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label} *"


class AjoutOrganisateurForm(forms.Form):
    username = forms.CharField(label='Nom d’utilisateur', max_length=MAX_USERNAME_TAILLE)

    def __init__(self, *args, **kwargs):
        self.epreuve = kwargs.pop('epreuve', None)  # Ajoute un argument epreuve au formulaire
        self.request_user = kwargs.pop('request_user', None)  # Utilisateur qui fait la requête
        super(AjoutOrganisateurForm, self).__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data['username']
        if self.request_user and username == self.request_user.username:
            raise forms.ValidationError("Vous ne pouvez pas vous ajouter vous-même.")

        try:
            organisateur_a_ajouter = User.objects.get(username=username)
            if not organisateur_a_ajouter.groups.filter(name='Organisateur').exists():
                raise forms.ValidationError("L'utilisateur n'a pas les privilèges nécessaires pour devenir membre "
                                            "d'un comité d'organisation.")
            if self.epreuve and MembreComite.objects.filter(membre=organisateur_a_ajouter,
                                                            epreuve=self.epreuve).exists():
                raise forms.ValidationError(f"{username} fait déjà partie du comité d'organisation "
                                            f"de l'épreuve {self.epreuve.nom}")
        except User.DoesNotExist:
            raise forms.ValidationError(f"L'utilisateur {username} est introuvable.")

        return username
