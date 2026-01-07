import random
from typing import List

from django.db import models
from django.contrib.auth.models import User
from django.db.models import QuerySet

from epreuve.models.epreuve import Epreuve
from epreuve.models.jeudetest import JeuDeTest
from epreuve.models.userepreuve import UserEpreuve
from epreuve.models.userexercice import UserExercice
from olympiadesnsi.constants import MAX_TAILLE_NOM
from olympiadesnsi.utils import encode_id


class Exercice(models.Model):
    TYPE_EXERCICE_CHOIX = [
        ('programmation', 'Programmation'),
        ('qcm', 'QCM'),
        ('qroc', 'QROC'),
        ('qcs', 'QCS')
    ]

    CODE_A_SOUMETTRE_CHOIX = [
        ("aucun", "Aucun code à soumettre"),
        ("python", "Code Python à soumettre"),
        ("autre", "Code dans un autre langage"),
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
    code_a_soumettre = models.CharField(
        max_length=10,
        choices=CODE_A_SOUMETTRE_CHOIX,
        default="python",
        null=True,
    )
    nombre_max_soumissions = models.IntegerField(default=50)
    numero = models.IntegerField(null=True, blank=True)

    @property
    def hashid(self) -> str:
        """
        Renvoie l'identifiant hashé de l'épreuve à utiliser dans les URLs.

        Returns:
            str: identifiant encodé (ex: pour usage dans les URLs).
        """
        return encode_id(self.id)

    @property
    def separateur_jeu_test_effectif(self) -> str:
        """Retourne le séparateur de jeu de test défini ou '\n' par défaut."""
        if self.separateur_jeu_test is not None:
            return self.separateur_jeu_test
        return "\n"

    @property
    def separateur_reponse_jeudetest_effectif(self) -> str :
        """Retourne le séparateur de réponse de jeu de test défini ou '\n' par défaut."""
        if self.separateur_reponse_jeudetest is not None:
            return self.separateur_reponse_jeudetest
        return '\n'

    def inscrire_utilisateurs_de_epreuve(self):
        """
        Pour tous les UserEpreuve associés à l’épreuve de cet exercice,
        crée un UserExercice si besoin pour ce participant et cet exercice.
        """
        user_epreuves: QuerySet[UserEpreuve] = UserEpreuve.objects.filter(epreuve=self.epreuve)

        for ue in user_epreuves:
            UserExercice.objects.get_or_create(
                exercice=self,
                participant=ue.participant
            )

    def assigner_jeux_de_test(self) -> None:
        """
        Attribue un jeu de test à chaque UserExercice associé à cet exercice.

        Les jeux de test sont attribués de manière cyclique et aléatoire.
        Si un UserExercice a déjà un jeu de test attribué, il est ignoré.
        """
        if not self.avec_jeu_de_test:
            return
        jeux_disponibles: List[JeuDeTest] = list(self.get_jeux_de_test())
        if not jeux_disponibles:
            return

        random.shuffle(jeux_disponibles)
        nb_jeux: int = len(jeux_disponibles)

        user_exercices: QuerySet[UserExercice] = self.user_exercices.all()

        for i, ue in enumerate(user_exercices):
            if ue.jeu_de_test:
                continue
            ue.jeu_de_test = jeux_disponibles[i % nb_jeux]
            ue.save()

    def pick_jeu_de_test(self) -> 'JeuDeTest':
        """
        Sélectionne aléatoirement un jeu de test associé à cet exercice.

        Returns:
            JeuDeTest: Un objet JeuDeTest sélectionné aléatoirement, ou None si aucun jeu de test n'est disponible.
        """
        return self.jeux_de_test.order_by('?').first()

    def get_jeux_de_test(self) -> QuerySet['JeuDeTest']:
        """
        Renvoie tous les jeux de tests_epreuve associés à cet exercice.

        Returns:
            QuerySet[JeuDeTest]: Les jeux de tests_epreuve liés à cet exercice.
        """
        return self.jeux_de_test.all()

    def vider_jeux_de_test(self) -> None:
        """
        Supprime tous les jeux de test associés à cet exercice,
        puis réinitialise les séparateurs à leur valeur par défaut.
        """
        self.jeux_de_test.all().delete()
        self.separateur_reponse_jeudetest = "\n"
        self.separateur_jeu_test = "\n"
        self.save(update_fields=["separateur_reponse_jeudetest", "separateur_jeu_test"])

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
