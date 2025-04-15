from django.contrib.auth.models import User
from django.db import models
from epreuve.models.jeudetest import JeuDeTest


class UserExercice(models.Model):
    participant = models.ForeignKey(User, related_name='user_exercices', on_delete=models.CASCADE)
    exercice = models.ForeignKey('Exercice', related_name='user_exercices', on_delete=models.CASCADE)
    jeu_de_test = models.ForeignKey(JeuDeTest, on_delete=models.SET_NULL, null=True, blank=True)
    solution_instance_participant = models.TextField(null=True)
    code_participant = models.TextField(null=True)
    nb_soumissions = models.IntegerField(default=0)

    class Meta:
        db_table = 'User_Exercice'
        unique_together = ['participant', 'exercice']
