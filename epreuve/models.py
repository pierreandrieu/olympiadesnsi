from typing import List
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
        return self.exercices.all()

    def est_close(self) -> bool:
        """
        Renvoie True SSI l'épreuve est close
        Returns: True SSI l'épreuve est close

        """
        return self.date_fin < timezone.now()

    def pas_commencee(self):
        """
        Détermine si l'épreuve n'a pas encore commencé.

        Returns:
            bool: True si l'épreuve n'a pas encore commencé, False autrement.
        """
        # timezone.now() donne l'heure actuelle de manière "aware" en fonction des paramètres de timezone de Django
        return self.date_debut > timezone.now()

    def compte_participants_inscrits(self) -> int:
        """
        Compte le nombre total de participants inscrits à l'épreuve par le biais de l'inscription externe.

        Returns:
            int: Le nombre total de participants inscrits.
        """
        # On récupère tous les groupes participants associés à cette épreuve
        groupes = self.groupes_participants.all()

        # On initialise un compteur
        total_participants = 0

        # Pour chaque groupe, on compte le nombre de membres et on ajoute ce nombre au total
        for groupe in groupes:
            total_participants += groupe.get_nombre_participants()

        return total_participants

    def a_pour_membre_comite(self, user: User) -> bool:
        """
        Détermine si l'utilisateur donné est un membre du comité d'organisation de cette épreuve.

        Args:
            user (User): L'utilisateur à vérifier.

        Returns:
            bool: True si l'utilisateur est membre du comité, False autrement.
        """
        # On utilise `self.comite` pour accéder directement à la relation ManyToMany via le modèle intermédiaire
        # et on vérifie si l'utilisateur est dans la liste des membres du comité.
        return self.comite.filter(id=user.id).exists()

    def doit_demander_identifiants(self) -> bool:
        """
        Retourne True SSI on veut récupérer, au moment de la première connexion pour
        une épreuve d'olympiades, les identifiants de l'épreuve papier.
        :return:
        """
        return ("lympiade" in self.nom and "2025" in self.nom and "entrainement" not in self.nom
                and "annale" not in self.nom and self.referent.username == "pierre.andrieu" )

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

    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE, related_name='exercices')
    auteur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    titre = models.CharField(max_length=MAX_TAILLE_NOM)
    bareme = models.IntegerField(null=True)
    type_exercice = models.CharField(max_length=14, choices=TYPE_EXERCICE_CHOIX, default="programmation")
    enonce = models.TextField(null=True, blank=True)
    enonce_code = models.TextField(null=True, blank=True)
    avec_jeu_de_test = models.BooleanField(default=False)
    separateur_jeu_test = models.CharField(null=True, blank=True)
    separateur_reponse_jeudetest = models.CharField(null=True, blank=True)
    retour_en_direct = models.BooleanField(default=False)
    code_a_soumettre = models.BooleanField(default=False)
    nombre_max_soumissions = models.IntegerField(default=50)
    numero = models.IntegerField(null=True, blank=True)

    @property
    def separateur_jeu_test_effectif(self):
        """Retourne le séparateur de jeu de test défini ou '\n' par défaut."""
        if self.separateur_jeu_test is not None:
            return self.separateur_jeu_test
        return "\n"

    @property
    def separateur_reponse_jeudetest_effectif(self):
        """Retourne le séparateur de réponse de jeu de test défini ou '\n' par défaut."""
        if self.separateur_reponse_jeudetest is not None:
            return self.separateur_reponse_jeudetest
        return '\n'

    def pick_jeu_de_test(self):
        """
        Sélectionne aléatoirement un jeu de test associé à cet exercice.

        Returns:
            JeuDeTest: Un objet JeuDeTest sélectionné aléatoirement, ou None si aucun jeu de test n'est disponible.
        """
        return self.jeudetest_set.order_by('?').first()

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
    participant = models.ForeignKey(User, related_name='user_epreuves',
                                    on_delete=models.CASCADE)
    epreuve = models.ForeignKey(Epreuve, related_name='participant_entries',
                                on_delete=models.CASCADE)
    debut_epreuve = models.DateTimeField(auto_now=False, null=True)
    anonymat = models.CharField(max_length=255, blank=True, null=True,
                                    help_text="Stocke les numéros d'anonymat des 3 participants séparés par '|'.")

    class Meta:
        db_table = 'UserEpreuve'
        indexes = [
            models.Index(fields=['participant', 'epreuve']),
            models.Index(fields=['epreuve', 'participant']),

        ]

        unique_together = ['participant', 'epreuve']

    def set_anonymat(self, anonymats: List[str]) -> None:
        """
        Enregistre les numéros d'anonymat sous la forme d'une chaîne formatée.
        Exemple : ["123", "?", "-"] => "123|?|-"
        """
        self.anonymat = "|".join(anonymats)
        self.save()

    def get_anonymat(self) -> List[str]:
        """
        Récupère les numéros d'anonymat sous forme de liste.
        Retourne ["123", "?", "-"] si l'entrée en BD est "123|?|-"
        """
        return self.anonymat.split("|") if self.anonymat else ["", "", ""]


class UserExercice(models.Model):
    participant = models.ForeignKey(User, related_name='user_exercices', on_delete=models.CASCADE)
    exercice = models.ForeignKey(Exercice, related_name='user_exercices', on_delete=models.CASCADE)
    jeu_de_test = models.ForeignKey(JeuDeTest, on_delete=models.SET_NULL, null=True, blank=True)
    solution_instance_participant = models.TextField(null=True)
    code_participant = models.TextField(null=True)
    nb_soumissions = models.IntegerField(default=0)

    class Meta:
        db_table = 'User_Exercice'
        unique_together = ['participant', 'exercice']
