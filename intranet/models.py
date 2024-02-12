from django.db import models
from django.contrib.auth.models import User, Group


class GroupeCreePar(models.Model):
    groupe = models.ForeignKey(Group, related_name='associations_groupe_createur', on_delete=models.CASCADE)
    createur = models.ForeignKey(User, related_name='groupes_crees', on_delete=models.CASCADE)
    nombre_participants = models.IntegerField(default=0)
    date_creation = models.DateField()

    def __str__(self):
        return f"{self.createur.username} -> {self.groupe.name}"

    class Meta:
        db_table = 'GroupeCreePar'
        indexes = [
            models.Index(fields=['createur']),
        ]

        unique_together = ['groupe', 'createur']
