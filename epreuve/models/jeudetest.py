from django.db import models


class JeuDeTest(models.Model):
    exercice = models.ForeignKey(
        'Exercice',
        on_delete=models.CASCADE,
        related_name='jeux_de_test'
    )
    instance = models.TextField(null=False)
    reponse = models.TextField(null=False)

    class Meta:
        db_table = 'JeuDeTest'
        indexes = [
            models.Index(fields=['exercice'])
        ]
