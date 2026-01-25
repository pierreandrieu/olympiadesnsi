from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

import olympiadesnsi.constants as constantes


# ---------------------------------------------------------------------
# Tokens / inscriptions externes
# ---------------------------------------------------------------------

class InscripteurExterne(models.Model):
    email = models.EmailField(primary_key=True, max_length=constantes.MAX_TAILLE_NOM)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "InscripteurExterne"

    def __str__(self) -> str:
        return self.email


class InscriptionExterne(models.Model):
    inscripteur = models.ForeignKey(
        "inscription.InscripteurExterne",
        on_delete=models.CASCADE,
        related_name="inscriptions_externes",
    )
    token = models.CharField(max_length=constantes.TOKEN_LENGTH, unique=True, blank=True)
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE, related_name="inscriptions_externes")
    date_creation = models.DateTimeField(auto_now_add=True)
    token_est_utilise = models.BooleanField(default=False)
    nombre_participants_demandes = models.IntegerField(default=0)

    @property
    def est_valide(self) -> bool:
        return (
                (not self.token_est_utilise)
                and (timezone.now() - self.date_creation < timedelta(hours=constantes.HEURES_VALIDITE_TOKEN))
        )

    class Meta:
        db_table = "InscriptionExterne"
        indexes = [models.Index(fields=["inscripteur"])]

    def __str__(self) -> str:
        return f"{self.inscripteur_id} - {self.epreuve_id} - {self.token}"


# ---------------------------------------------------------------------
# Référentiel établissement
# ---------------------------------------------------------------------

class Etablissement(models.Model):
    code_uai = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        help_text="Code UAI (ex: 0781234A).",
    )
    nom = models.CharField(max_length=constantes.MAX_TAILLE_NOM, blank=True, default="")
    commune = models.CharField(max_length=constantes.MAX_TAILLE_NOM, blank=True, default="")
    email = models.EmailField(max_length=constantes.MAX_TAILLE_NOM, blank=True, default="")

    date_creation = models.DateTimeField(auto_now_add=True)
    date_maj = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "Etablissement"
        indexes = [models.Index(fields=["code_uai"])]

    def __str__(self) -> str:
        return f"{self.code_uai} - {self.nom or '(nom non renseigné)'}"


# ---------------------------------------------------------------------
# Inscription olympiades (par établissement + prof)
# ---------------------------------------------------------------------

class InscriptionOlympiades(models.Model):
    """
    Inscription d'un établissement aux Olympiades, portée par un email enseignant.

    Un établissement peut être inscrit plusieurs fois (plusieurs enseignants) :
    unicité sur (epreuve, etablissement, email_enseignant).
    """

    epreuve = models.ForeignKey(
        "epreuve.Epreuve",
        on_delete=models.CASCADE,
        related_name="inscriptions_olympiades",
    )

    etablissement = models.ForeignKey(
        "inscription.Etablissement",
        on_delete=models.PROTECT,
        related_name="inscriptions_olympiades",
    )

    code_uai = models.CharField(
        max_length=16,
        db_index=True,
        help_text="Code UAI de l'établissement (ex: 0781234A).",
    )

    email_enseignant = models.EmailField(
        max_length=constantes.MAX_TAILLE_NOM,
        help_text="Email académique du professeur (contact).",
    )

    nom_enseignant = models.CharField(
        max_length=constantes.MAX_TAILLE_NOM,
        blank=True,
        help_text="Nom (ou nom+prénom) de l'enseignant de contact.",
    )

    nb_candidats_ecrit = models.IntegerField(
        default=0,
        help_text="Nombre de candidats pour l'épreuve écrite (individuelle).",
    )

    nb_equipes_pratique = models.IntegerField(
        default=0,
        help_text="Nombre d'équipes pour l'épreuve pratique (1 à 3 élèves).",
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_maj = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "InscriptionOlympiades"
        constraints = [
            models.UniqueConstraint(
                fields=["epreuve", "etablissement", "email_enseignant"],
                name="unique_epreuve_etablissement_email_enseignant",
            )
        ]
        indexes = [
            models.Index(fields=["epreuve", "code_uai"]),
            models.Index(fields=["code_uai"]),
        ]

    def __str__(self) -> str:
        return f"{self.code_uai} ({self.email_enseignant}) - {self.epreuve_id}"


class InscriptionOlympiadesGroupe(models.Model):
    TYPE_OLYMPIADES = "olympiades"
    TYPE_ANNALES = "annales"

    TYPE_CHOIX = [
        (TYPE_OLYMPIADES, "Olympiades"),
        (TYPE_ANNALES, "Annales"),
    ]

    inscription = models.ForeignKey(
        "inscription.InscriptionOlympiades",
        on_delete=models.CASCADE,
        related_name="groupes_associes",
    )

    groupe = models.ForeignKey(
        "intranet.GroupeParticipant",
        on_delete=models.CASCADE,
        related_name="inscriptions_olympiades_associees",
    )

    type_groupe = models.CharField(max_length=16, choices=TYPE_CHOIX)
    numero = models.PositiveIntegerField(default=1)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "InscriptionOlympiadesGroupe"
        constraints = [
            models.UniqueConstraint(
                fields=["inscription", "type_groupe", "numero"],
                name="unique_inscription_type_numero",
            ),
            models.UniqueConstraint(
                fields=["inscription", "groupe"],
                name="unique_inscription_groupe",
            ),
        ]
        indexes = [
            models.Index(fields=["inscription", "type_groupe"]),
        ]

    def __str__(self) -> str:
        return f"{self.inscription_id} - {self.type_groupe} - {self.numero}"


# ---------------------------------------------------------------------
# Domaines autorisés (demande de lien)
# ---------------------------------------------------------------------

class InscriptionDomaine(models.Model):
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE, related_name="domaines_inscription")
    domaine = models.CharField(max_length=constantes.MAX_TAILLE_NOM)

    class Meta:
        db_table = "Inscription_domaine"
        indexes = [models.Index(fields=["epreuve"])]

    def __str__(self) -> str:
        return f"{self.epreuve_id} - {self.domaine}"


# ---------------------------------------------------------------------
# Lien groupe <-> épreuve (si tu ne l'as pas déjà ailleurs)
# ---------------------------------------------------------------------

class GroupeParticipeAEpreuve(models.Model):
    groupe = models.ForeignKey("intranet.GroupeParticipant", on_delete=models.CASCADE)
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE)

    class Meta:
        db_table = "GroupeParticipeAEpreuve"
        unique_together = ["groupe", "epreuve"]
        indexes = [
            models.Index(fields=["groupe"]),
            models.Index(fields=["epreuve"]),
        ]

    def __str__(self) -> str:
        return f"{self.groupe_id} - {self.epreuve_id}"


# ---------------------------------------------------------------------
# Annales (plateforme uniquement)
# ---------------------------------------------------------------------

class InscriptionAnnales(models.Model):
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE, related_name="inscriptions_annales")
    email_enseignant = models.EmailField(max_length=constantes.MAX_TAILLE_NOM)
    nom_enseignant = models.CharField(max_length=constantes.MAX_TAILLE_NOM, blank=True, default="")

    groupes_associes = models.ManyToManyField(
        "intranet.GroupeParticipant",
        related_name="inscriptions_annales_associees",
        blank=True,
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_maj = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "InscriptionAnnales"
        constraints = [
            models.UniqueConstraint(
                fields=["epreuve", "email_enseignant"],
                name="unique_epreuve_email_annales",
            )
        ]
        indexes = [
            models.Index(fields=["epreuve", "email_enseignant"]),
        ]

    def __str__(self) -> str:
        return f"Annales {self.epreuve_id} - {self.email_enseignant}"


# ---------------------------------------------------------------------
# Compteur (si toujours utilisé)
# ---------------------------------------------------------------------

class CompteurParticipantsAssocies(models.Model):
    organisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="compteur_participants_associes",
    )
    nb_participants_associes = models.IntegerField(default=0)

    class Meta:
        db_table = "Organisateur_CompteurParticipant"
        verbose_name = "compteur de participants associes à organisateur"
        verbose_name_plural = "compteurs de participants associes à organisateur"

    def __str__(self) -> str:
        # Safe même si custom user model : __str__ gère généralement le username
        return f"{self.organisateur} -> {self.nb_participants_associes} participants associés"


# ---------------------------------------------------------------------
# Anonymats épreuve écrite
# ---------------------------------------------------------------------

class AnonymatEpreuveEcrite(models.Model):
    """
    Réservation d'un anonymat pour l'épreuve écrite (UAI + 3 chiffres).

    Unicité partielle sur les anonymats actifs (Postgres) :
        (epreuve, etablissement, numero) unique si actif=True.
    """

    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE, related_name="anonymats_ecrits")

    etablissement = models.ForeignKey(
        "inscription.Etablissement",
        on_delete=models.PROTECT,
        related_name="anonymats_ecrits",
    )

    numero = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(999)],
        help_text="Numéro 0..999 correspondant aux 3 chiffres après l'UAI.",
    )

    actif = models.BooleanField(default=True)

    inscription = models.ForeignKey(
        "inscription.InscriptionOlympiades",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anonymats_ecrits",
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["epreuve", "etablissement", "numero"],
                condition=Q(actif=True),
                name="uniq_anonymat_actif_par_epreuve_etab_numero",
            )
        ]
        indexes = [
            models.Index(fields=["epreuve", "etablissement", "actif"]),
            models.Index(fields=["inscription", "actif"]),
        ]

    def __str__(self) -> str:
        return f"{self.epreuve_id} / {self.etablissement_id} / {self.numero:03d} / actif={self.actif}"
