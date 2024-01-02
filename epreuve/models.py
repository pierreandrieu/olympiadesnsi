from django.db import models
from django.contrib.auth.models import User, Group


class Epreuve(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField()
    date_debut = models.DateField()
    date_fin = models.DateField()
    duree = models.IntegerField()  # Durée en minutes
    referent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='epreuve_referent')
    exercices_un_par_un = models.BooleanField(default=False)
    soumissions_max_par_exercices = models.IntegerField()
    temps_limite = models.BooleanField(default=False)
    presence_flag = models.BooleanField(default=False)
    code_a_soumettre = models.BooleanField(default=False)
    groupes_participants = models.ManyToManyField(Group, related_name='epreuves', through='GroupeParticipeAEpreuve')
    comite = models.ManyToManyField(User, related_name='epreuves_comite', through='MembreComite')

    def __str__(self):
        return self.nom

    class Meta:
        db_table = 'Epreuve'


class GroupeParticipeAEpreuve(models.Model):
    groupe = models.ForeignKey(Group, on_delete=models.CASCADE)
    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE)

    class Meta:
        db_table = 'GroupeParticipeAEpreuve'


class MembreComite(models.Model):
    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE)
    membre = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'MembreComite'


class CreePar(models.Model):
    utilisateur = models.ForeignKey(User, related_name='associations', on_delete=models.CASCADE)
    createur = models.ForeignKey(User, related_name='utilisateurs_crees', on_delete=models.CASCADE)
    date_creation = models.DateField()

    def __str__(self):
        return f"{self.createur.username} -> {self.utilisateur.username}"

    class Meta:
        db_table = 'UserCreePar'
