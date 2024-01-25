from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models import CheckConstraint, Q, F


class Epreuve(models.Model):
    nom = models.CharField(max_length=100)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    duree = models.IntegerField(null=True)  # Durée en minutes
    referent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='epreuve_referent')
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


class Exercice(models.Model):
    TYPE_EXERCICE_CHOIX = [
        ('programmation', 'Programmation'),
        ('qcm', 'QCM'),
        ('qroc', 'QROC'),
        ('qcs', 'QCS')
    ]

    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE)
    auteur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    titre = models.CharField(max_length=100)
    bareme = models.IntegerField(null=True)
    type_exercice = models.CharField(max_length=14, choices=TYPE_EXERCICE_CHOIX, default="programmation")
    enonce = models.TextField(null=True, blank=True)
    enonce_code = models.TextField(null=True, blank=True)
    avec_jeu_de_test = models.BooleanField(default=False)
    retour_en_direct = models.BooleanField(default=False)
    code_a_soumettre = models.BooleanField(default=False)
    nombre_max_soumissions = models.IntegerField(default=50)
    numero = models.IntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Si le numéro n'est pas déjà défini (nouvel exercice)
        if self.numero is None:
            # On récupère le plus grand numéro existant pour cette épreuve
            dernier_numero = Exercice.objects.filter(epreuve=self.epreuve).aggregate(max_numero=models.Max('numero'))[
                'max_numero']
            # Si aucun exercice n'existe, on commence à 1, sinon on ajoute 1 au plus grand numéro
            self.numero = 1 if dernier_numero is None else dernier_numero + 1

        super().save(*args, **kwargs)

    class Meta:
        db_table = 'Exercice'
        indexes = [
            models.Index(fields=['epreuve']),
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
        unique_together = ['groupe', 'epreuve']


class MembreComite(models.Model):
    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE)
    membre = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'MembreComite'
        unique_together = ['epreuve', 'membre']
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

        unique_together = ['groupe', 'createur']


class UserEpreuve(models.Model):
    participant = models.ForeignKey(User, related_name='association_UserEpreuve_User',
                                    on_delete=models.CASCADE)
    epreuve = models.ForeignKey(Epreuve, related_name='association_UserEpreuve_Epreuve',
                                 on_delete=models.CASCADE)
    fin_epreuve = models.DateTimeField(auto_now=False, null=True)


    class Meta:
        db_table = 'UserEpreuve'

        indexes = [
            models.Index(fields=['participant', 'epreuve']),
            models.Index(fields=['epreuve', 'participant']),

        ]

        unique_together = ['participant', 'epreuve']


class JeuDeTest(models.Model):
    exercice = models.ForeignKey(Exercice, on_delete=models.CASCADE)
    instance = models.TextField(null=False)
    reponse = models.TextField(null=False)
    class Meta:
        db_table = 'JeuDeTest'

        indexes = [
            models.Index(fields=['exercice'])
        ]


class UserExercice(models.Model):
    participant = models.ForeignKey(User, related_name='association_UserExercice_User',
                                    on_delete=models.CASCADE)
    exercice = models.ForeignKey(Exercice, related_name='association_UserExercice_Exercice', on_delete=models.CASCADE)
    jeu_de_test = models.ForeignKey(JeuDeTest, on_delete=models.SET_NULL, null=True, blank=True)
    solution_instance_participant = models.TextField(null=True)
    code_participant = models.TextField(null=True)
    nb_soumissions = models.IntegerField(default=0)

    class Meta:
        db_table = 'ParticipantExercice'
