from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import User, Group
from django.db.models import CheckConstraint, Q, F, QuerySet
from inscription.models import GroupeParticipant
from olympiadesnsi.constants import MAX_TAILLE_NOM


class Epreuve(models.Model):
    nom = models.CharField(max_length=MAX_TAILLE_NOM)
    code = models.CharField(max_length=255, unique=True, blank=False, null=False)
    date_debut = models.DateTimeField(null=False, blank=False)
    date_fin = models.DateTimeField(null=False, blank=False)
    duree = models.IntegerField(null=True)  # Durée en minutes
    referent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='epreuve_referent')
    exercices_un_par_un = models.BooleanField(default=False)
    temps_limite = models.BooleanField(default=False)
    inscription_externe = models.BooleanField(default=False)
    groupes_participants = models.ManyToManyField(GroupeParticipant, related_name='epreuves',
                                                  through='inscription.GroupeParticipeAEpreuve')
    comite = models.ManyToManyField(User, related_name='epreuves_comite', through='MembreComite')

    def get_exercices(self) -> QuerySet['Exercice']:
        """
        Renvoie tous les exercices associés à cette épreuve.

        Returns:
            QuerySet[Exercice]: Un QuerySet contenant les exercices associés à l'épreuve.
        """
        return self.exercice_set.all()

    def est_close(self) -> bool:
        """
        Renvoie True SSI l'épreuve est close
        Returns: True SSI l'épreuve est close

        """
        return self.date_fin < timezone.now()

    def pas_commencee(self):
        """
        Détermine si l'épreuve n'a pas encore commencé.

        Retourne:
            bool: True si l'épreuve n'a pas encore commencé, False autrement.
        """
        # timezone.now() donne l'heure actuelle de manière "aware" en fonction des paramètres de timezone de Django
        return self.date_debut > timezone.now()


    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.id:  # L'objet n'a pas encore été enregistré dans la base de données
            self.clean()
            super().save(*args, **kwargs)  # Sauvegarde préalable pour obtenir un ID
        # Générer le code unique
        nom_formatte = slugify(self.nom)[:50]  # Limite à 50 caractères et remplace les espaces par des tirets
        self.code = f"{self.id:03d}_{nom_formatte}"
        super().save(*args, **kwargs)  # Sauvegarde finale avec le code unique

    class Meta:
        db_table = 'Epreuve'
        unique_together = ['nom', 'referent']
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
    titre = models.CharField(max_length=MAX_TAILLE_NOM)
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
        unique_together = ['epreuve', 'titre']

        indexes = [
            models.Index(fields=['epreuve']),
        ]


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


class JeuDeTest(models.Model):
    exercice = models.ForeignKey(Exercice, on_delete=models.CASCADE)
    instance = models.TextField(null=False)
    reponse = models.TextField(null=False)

    class Meta:
        db_table = 'JeuDeTest'

        indexes = [
            models.Index(fields=['exercice'])
        ]


class UserEpreuve(models.Model):
    participant = models.ForeignKey(User, related_name='association_UserEpreuve_User',
                                    on_delete=models.CASCADE)
    epreuve = models.ForeignKey(Epreuve, related_name='association_UserEpreuve_Epreuve',
                                on_delete=models.CASCADE)
    debut_epreuve = models.DateTimeField(auto_now=False, null=True)

    class Meta:
        db_table = 'UserEpreuve'
        indexes = [
            models.Index(fields=['participant', 'epreuve']),
            models.Index(fields=['epreuve', 'participant']),

        ]

        unique_together = ['participant', 'epreuve']


class UserExercice(models.Model):
    participant = models.ForeignKey(User, related_name='association_UserExercice_User',
                                    on_delete=models.CASCADE)
    exercice = models.ForeignKey(Exercice, related_name='association_UserExercice_Exercice', on_delete=models.CASCADE)
    jeu_de_test = models.ForeignKey(JeuDeTest, on_delete=models.SET_NULL, null=True, blank=True)
    solution_instance_participant = models.TextField(null=True)
    code_participant = models.TextField(null=True)
    nb_soumissions = models.IntegerField(default=0)

    class Meta:
        db_table = 'User_Exercice'
        unique_together = ['participant', 'exercice']
