from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from epreuve.models.exercice import Exercice


class JeuDeTest(models.Model):
    exercice = models.ForeignKey('Exercice', on_delete=models.CASCADE)
    instance = models.TextField(null=False)
    reponse = models.TextField(null=False)

    class Meta:
        db_table = 'JeuDeTest'

        indexes = [
            models.Index(fields=['exercice'])
        ]

