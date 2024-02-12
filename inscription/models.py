from django.contrib.auth.models import Group
from django.utils.crypto import get_random_string
from django.db import models
from django.utils import timezone
from datetime import timedelta
from epreuve.models import Epreuve


class Inscripteur(models.Model):
    email = models.EmailField()
    token = models.CharField(max_length=100, unique=True, blank=True)
    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE)
    date_creation = models.DateTimeField(auto_now_add=True)
    est_utilise = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = get_random_string(50)  # Génère un token aléatoire
        super().save(*args, **kwargs)

    @property
    def est_valide(self):
        """Vérifie si l'invitation est encore valide (par exemple, non expirée)."""
        return not self.est_utilise and (timezone.now() - self.date_creation < timedelta(hours=1))

    class Meta:
        db_table = 'Inscripteur'


class GroupeParticipeAEpreuve(models.Model):
    groupe = models.ForeignKey(Group, on_delete=models.CASCADE)
    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE)

    class Meta:
        db_table = 'GroupeParticipeAEpreuve'
        indexes = [
            models.Index(fields=['groupe', 'epreuve']),
            models.Index(fields=['epreuve']),

        ]
        unique_together = ['groupe', 'epreuve']


class Inscription_domaine(models.Model):
    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE)
    domaine = models.CharField(max_length=100)

    class Meta:
        db_table = 'Inscription_domaine'

        indexes = [
            models.Index(fields=['epreuve']),
        ]