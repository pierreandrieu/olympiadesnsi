from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models import CheckConstraint, Q, F


class Epreuve(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField()
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    duree = models.IntegerField()  # Durée en minutes
    referent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='epreuve_referent')
    exercices_un_par_un = models.BooleanField(default=False)
    temps_limite = models.BooleanField(default=False)
    groupes_participants = models.ManyToManyField(Group, related_name='epreuves', through='GroupeParticipeAEpreuve')
    comite = models.ManyToManyField(User, related_name='epreuves_comite', through='MembreComite')

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'Epreuve'
        constraints = [
            CheckConstraint(
                check=Q(
                    Q(date_debut__isnull=True) |
                    Q(date_fin__isnull=True) |
                    Q(date_fin__gte=F('date_debut'))
                ),
                name='date_fin_apres_ou_egale_a_date_debut_si_non_null'
            )
        ]
        indexes = [
            models.Index(fields=['referent']),
        ]


class GroupeParticipeAEpreuve(models.Model):
    groupe = models.ForeignKey(Group, on_delete=models.CASCADE)
    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE)

    class Meta:
        db_table = 'GroupeParticipeAEpreuve'
        indexes = [
            models.Index(fields=['groupe', 'epreuve']),
            models.Index(fields=['epreuve']),

        ]


class MembreComite(models.Model):
    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE)
    membre = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'MembreComite'
        indexes = [
            models.Index(fields=['epreuve', 'membre']),
            models.Index(fields=['membre', 'epreuve']),
        ]


class UserCreePar(models.Model):
    utilisateur = models.ForeignKey(User, related_name='associations', on_delete=models.CASCADE)
    createur = models.ForeignKey(User, related_name='utilisateurs_crees', on_delete=models.CASCADE)
    date_creation = models.DateField()

    def __str__(self):
        return f"{self.createur.username} -> {self.utilisateur.username}"

    class Meta:
        db_table = 'UserCreePar'
        indexes = [
            models.Index(fields=['createur']),
        ]


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

