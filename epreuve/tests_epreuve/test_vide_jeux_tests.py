from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from epreuve.models import Exercice, Epreuve, JeuDeTest


def creer_exercice(
        epreuve: Epreuve,
        auteur: User,
        titre: str = "Exercice test",
        type_exercice: str = "programmation",
        avec_jeu_de_test: bool = False,
        retour_en_direct: bool = False
) -> Exercice:
    """
    Crée un exercice minimal valide pour les tests.
    """
    return Exercice.objects.create(
        epreuve=epreuve,
        auteur=auteur,
        titre=titre,
        type_exercice=type_exercice,
        avec_jeu_de_test=avec_jeu_de_test,
        retour_en_direct=retour_en_direct
    )


class ExerciceJeuDeTestTests(TestCase):
    def setUp(self):
        # Création d’un utilisateur
        self.user = User.objects.create_user(username="testuser", password="pass")

        # Création d’une épreuve
        now = timezone.now()
        self.epreuve = Epreuve.objects.create(
            nom="Epreuve test",
            code="code",
            date_debut=now,
            date_fin=now + timedelta(hours=1),
            referent=self.user,
        )

        # Création de l’exercice et des jeux de test
        self.exercice = creer_exercice(epreuve=self.epreuve, auteur=self.user, avec_jeu_de_test=True)
        for i in range(3):
            JeuDeTest.objects.create(exercice=self.exercice, instance=f"Entrée {i}", reponse=f"Sortie {i}")

        self.exercice.separateur_jeu_test = "|"
        self.exercice.separateur_reponse_jeudetest = ";"
        self.exercice.save()

    def test_vider_jeux_de_test_supprime_tout(self):
        """
        Vérifie que la méthode `vider_jeux_de_test()` supprime tous les jeux
        et réinitialise les séparateurs.
        """
        self.assertEqual(JeuDeTest.objects.filter(exercice=self.exercice).count(), 3)

        self.exercice.vider_jeux_de_test()

        self.assertEqual(JeuDeTest.objects.filter(exercice=self.exercice).count(), 0)

        self.exercice.refresh_from_db()
        self.assertEqual(self.exercice.separateur_reponse_jeudetest, "\n")
        self.assertEqual(self.exercice.separateur_jeu_test, "\n")
