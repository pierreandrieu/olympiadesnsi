from typing import cast, List

from captcha.fields import CaptchaField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Submit
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _
from olympiadesnsi import settings
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


class DemandeLienOlympiadesForm(forms.Form):
    """
    Demande d'envoi d'un lien tokenisé à un enseignant.

    L'utilisateur saisit :
    - la partie gauche de l'email (identifiant),
    - choisit un domaine autorisé (récupéré via l'épreuve courante),
    - éventuellement un captcha si activé.
    """

    identifiant = forms.CharField(
        label=_("Identifiant académique"),
        max_length=constantes.MAX_TAILLE_NOM,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    domaine_academique = forms.ChoiceField(
        label=_("Domaine académique"),
        choices=[],
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    consentement = forms.BooleanField(
        label=_("Je certifie réaliser cette inscription en tant qu'enseignant de NSI pour un établissement."),
        required=True,
    )

    def __init__(self, *args, domaines: List[str] | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Remplit dynamiquement la liste des domaines autorisés
        domaines_effectifs: List[str] = domaines or []
        self.fields["domaine_academique"].choices = [("", _("Sélectionnez un domaine"))] + [
            (d, d) for d in domaines_effectifs
        ]

        # Captcha optionnel (piloté par settings.CAPTCHA)
        if getattr(settings, "CAPTCHA", True):
            self.fields["captcha"] = CaptchaField(
                required=True,
                error_messages={"required": _("Veuillez résoudre le captcha.")},
            )
            self.fields["captcha"].widget.attrs.update({"class": "form-control"})

    def clean_identifiant(self) -> str:
        """
        Nettoie l'identifiant et interdit l'utilisation directe d'un email complet.
        """
        identifiant_brut: str = self.cleaned_data["identifiant"]
        identifiant: str = identifiant_brut.strip()

        if "@" in identifiant:
            raise ValidationError(_("Ne saisissez pas l'email complet : uniquement la partie avant @."))

        if not identifiant:
            raise ValidationError(_("Veuillez saisir votre identifiant."))

        return identifiant


class InscriptionOlympiadesForm(forms.Form):
    """
    Formulaire d'inscription accessible via un lien tokenisé.

    Remarque : l'email enseignant vient du token et n'est pas un champ du formulaire.
    """

    # UAI : 7 caractères alphanumériques (en pratique souvent 7, parfois avec lettres)
    code_uai = forms.CharField(
        label="Code UAI",
        max_length=8,
        strip=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9A-Za-z]{7,8}$",
                message="Le code UAI doit contenir 7 ou 8 caractères alphanumériques.",
            )
        ],
        help_text="7 ou 8 caractères (lettres/chiffres). Exemple : 0751234A",
    )

    nom_etablissement = forms.CharField(
        label="Nom de l’établissement",
        max_length=255,
        required=True,
        strip=True,
    )

    commune = forms.CharField(
        label="Commune",
        max_length=255,
        required=True,
        strip=True,
    )

    email_etablissement = forms.EmailField(
        label="Email de l’établissement",
        required=True,
    )

    nom_enseignant = forms.CharField(
        label="Nom de l’enseignant",
        max_length=255,
        required=True,
        strip=True,
    )

    nb_candidats_ecrit = forms.IntegerField(
        label="Nombre de candidats pour l’épreuve écrite",
        required=True,
        validators=[MinValueValidator(0)],
        initial=0,

    )

    nb_equipes_pratique = forms.IntegerField(
        label="Nombre d’équipes pour l’épreuve pratique",
        required=True,
        validators=[MinValueValidator(0)],
        initial=0,
        help_text="Une équipe = un compte plateforme généré pour l’épreuve pratique.",
    )

    def clean_code_uai(self) -> str:
        code_uai = (self.cleaned_data.get("code_uai") or "").strip().upper()
        # On normalise en uppercase pour éviter les doublons "a" vs "A"
        return code_uai

    def clean(self) -> dict:
        cleaned = super().clean()

        nb_candidats_ecrit = cleaned.get("nb_candidats_ecrit")
        nb_equipes_pratique = cleaned.get("nb_equipes_pratique")

        # Si l’un est None (champ invalide), on ne rajoute pas d’erreur globale.
        if nb_candidats_ecrit is None or nb_equipes_pratique is None:
            return cleaned

        if nb_candidats_ecrit == 0 and nb_equipes_pratique == 0:
            raise forms.ValidationError(
                "Il faut inscrire au moins un candidat à l’épreuve écrite ou au moins une équipe à l’épreuve pratique."
            )

        return cleaned


class InscriptionOlympiadesEditionForm(forms.Form):
    """
    Formulaire d'édition :
    - modifier le nombre de candidats papier
    - ajouter un nouveau groupe pratique (bouton +) via nb_equipes_a_ajouter
    """

    nb_candidats_ecrit = forms.IntegerField(
        label=_("Nombre de candidats (épreuve écrite)"),
        min_value=0,
        required=True,
    )

    nb_equipes_a_ajouter = forms.IntegerField(
        label=_("Ajouter un groupe (nombre d'équipes dans ce nouveau groupe)"),
        min_value=0,
        required=False,
        initial=0,
        help_text=_("Mettre 0 pour ne pas ajouter de nouveau groupe."),
    )


class EditionInscriptionOlympiadesForm(forms.Form):
    nb_candidats_ecrit = forms.IntegerField(
        label="Nombre de candidats (papier)",
        validators=[MinValueValidator(0)],
    )
    nb_equipes_a_ajouter = forms.IntegerField(
        label="Nombre d’équipes à ajouter",
        validators=[MinValueValidator(0)],
        required=False,
        initial=0,
    )

    def clean_nb_equipes_a_ajouter(self) -> int:
        return int(self.cleaned_data.get("nb_equipes_a_ajouter") or 0)


class InscriptionAnnalesForm(forms.Form):
    nb_equipes = forms.IntegerField(
        label="Nombre d’équipes à générer",
        validators=[MinValueValidator(1)],
        initial=1,
        help_text="Un compte plateforme par équipe (mot de passe à définir à la première connexion).",
    )