from django.contrib.auth.models import Group, User
from django.utils.crypto import get_random_string
from django.db import models
from django.utils import timezone
from datetime import timedelta
#from epreuve.models import Epreuve
from intranet.models import GroupeParticipant


class Inscripteur(models.Model):
    email = models.EmailField()
    token = models.CharField(max_length=100, unique=True, blank=True)
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE)
    date_creation = models.DateTimeField(auto_now_add=True)
    token_est_utilise = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = get_random_string(50)  # Génère un token aléatoire
        super().save(*args, **kwargs)

    @property
    def est_valide(self):
        """Vérifie si l'invitation est encore valide (par exemple, non expirée)."""
        return not self.token_est_utilise and (timezone.now() - self.date_creation < timedelta(hours=1))

    class Meta:
        db_table = 'Inscripteur'


class GroupeParticipeAEpreuve(models.Model):
    groupe = models.ForeignKey(GroupeParticipant, on_delete=models.CASCADE)
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE)

    class Meta:
        db_table = 'GroupeParticipeAEpreuve'
        indexes = [
            models.Index(fields=['groupe', 'epreuve']),
            models.Index(fields=['epreuve']),

        ]
        unique_together = ['groupe', 'epreuve']


class InscriptionDomaine(models.Model):
    epreuve = models.ForeignKey("epreuve.Epreuve", on_delete=models.CASCADE)
    domaine = models.CharField(max_length=100)

    class Meta:
        db_table = 'Inscription_domaine'

        indexes = [
            models.Index(fields=['epreuve']),
        ]


class CompteurParticipantsAssocies(models.Model):
    organisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='User_CompteurParticipantsAssocies')
    nb_participants_associes = models.IntegerField(default=0, null=False, blank=False)

    class Meta:
        db_table = 'Organisateur_CompteurParticipant'
        indexes = [
            models.Index(fields=['organisateur']),
        ]
        verbose_name = 'compteur de participants associes à organisateur'
        verbose_name_plural = 'compteurs de participants associes à organisateur'

    def __str__(self):
        return f"{self.organisateur.username} -> {self.nb_participants_associes} participants associés"