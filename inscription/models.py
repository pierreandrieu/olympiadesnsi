from django.contrib.auth.models import Group, User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from datetime import timedelta
from intranet.models import GroupeParticipant
import olympiadesnsi.constants as constantes


class InscripteurExterne(models.Model):
    email = models.EmailField(primary_key=True, max_length=constantes.MAX_TAILLE_NOM)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'InscripteurExterne'


class InscriptionExterne(models.Model):
    inscripteur = models.ForeignKey(InscripteurExterne, on_delete=models.CASCADE)
    token = models.CharField(max_length=constantes.TOKEN_LENGTH, unique=True, blank=True)
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE)
    date_creation = models.DateTimeField(auto_now_add=True)
    token_est_utilise = models.BooleanField(default=False)
    nombre_participants_demandes = models.IntegerField(default=0)

    @property
    def est_valide(self):
        # Vérifie si l'invitation est encore valide (pas encore utilisé et non expirée).
        return not self.token_est_utilise and (timezone.now() - self.date_creation <
                                               timedelta(hours=constantes.HEURES_VALIDITE_TOKEN))

    class Meta:
        db_table = 'InscriptionExterne'
        indexes = [
            models.Index(fields=['inscripteur']),
        ]


class GroupeParticipeAEpreuve(models.Model):
    groupe = models.ForeignKey(GroupeParticipant, on_delete=models.CASCADE)
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE)

    class Meta:
        db_table = 'GroupeParticipeAEpreuve'
        indexes = [
            models.Index(fields=['groupe']),
            models.Index(fields=['epreuve']),

        ]
        unique_together = ['groupe', 'epreuve']


class InscriptionDomaine(models.Model):
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE)
    domaine = models.CharField(max_length=constantes.MAX_TAILLE_NOM)

    class Meta:
        db_table = 'Inscription_domaine'

        indexes = [
            models.Index(fields=['epreuve']),
        ]


class CompteurParticipantsAssocies(models.Model):
    organisateur = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True,
                                        related_name='compteur_participants_associes')
    nb_participants_associes = models.IntegerField(default=0, null=False, blank=False)

    class Meta:
        db_table = 'Organisateur_CompteurParticipant'
        verbose_name = 'compteur de participants associes à organisateur'
        verbose_name_plural = 'compteurs de participants associes à organisateur'

    def __str__(self):
        return f"{self.organisateur.username} -> {self.nb_participants_associes} participants associés"


class InscriptionOlympiades(models.Model):
    """
    Stocke les informations d'inscription d'un établissement (et d'un professeur référent)
    aux Olympiades (épreuve courante gérée par la plateforme).

    Un établissement peut avoir plusieurs professeurs de NSI inscrivant leurs propres équipes :
    l'unicité repose donc sur (épreuve, UAI, email_enseignant).
    """

    epreuve = models.ForeignKey(
        "epreuve.Epreuve",
        on_delete=models.CASCADE,
        related_name="inscriptions_olympiades",
    )

    code_uai = models.CharField(
        max_length=16,
        null=False,
        blank=False,
        db_index=True,
        help_text="Code UAI de l'établissement (ex: 0781234A).",
    )

    # Email de contact (prof de NSI) : issu du lien tokenisé (InscripteurExterne.email)
    email_enseignant = models.EmailField(
        max_length=constantes.MAX_TAILLE_NOM,
        null=False,
        blank=False,
        help_text="Email académique du professeur (contact).",
    )

     # Nom/prénom prof (info) : l’email fait foi pour le contact
    nom_enseignant = models.CharField(
        max_length=constantes.MAX_TAILLE_NOM,
        null=False,
        blank=True,
        help_text="Nom (ou nom+prénom) de l'enseignant de contact.",
    )

    # Volumes
    nb_candidats_ecrit = models.IntegerField(
        null=False,
        blank=False,
        default=0,
        help_text="Nombre de candidats pour l'épreuve écrite (individuelle).",
    )
    nb_equipes_pratique = models.IntegerField(
        null=False,
        blank=False,
        default=0,
        help_text="Nombre d'équipes pour l'épreuve pratique (1 à 3 élèves).",
    )

    etablissement = models.ForeignKey(
        "inscription.Etablissement",
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        related_name="inscriptions_olympiades",
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
        "intranet.GroupeParticipant",  # adapte si ton GroupeParticipant est ailleurs
        on_delete=models.CASCADE,
        related_name="inscriptions_olympiades_associees",
    )

    type_groupe = models.CharField(
        max_length=16,
        choices=TYPE_CHOIX,
        null=False,
        blank=False,
    )

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


class InscriptionAnnales(models.Model):
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE, related_name="inscriptions_annales")

    email_enseignant = models.EmailField(max_length=constantes.MAX_TAILLE_NOM)
    nom_enseignant = models.CharField(max_length=constantes.MAX_TAILLE_NOM, blank=True, default="")

    date_creation = models.DateTimeField(auto_now_add=True)
    date_maj = models.DateTimeField(auto_now=True)
    groupes_associes = models.ManyToManyField(
        "intranet.GroupeParticipant",
        related_name="inscriptions_annales_associees",
        blank=True,
    )

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
