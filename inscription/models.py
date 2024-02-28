from django.contrib.auth.models import Group, User
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
