from django.test import TestCase
from django.contrib.auth.models import User
from django.utils.timezone import now, timedelta
from epreuve.models import Epreuve, UserEpreuve


class TempsRestantUserEpreuveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser")
        self.epreuve = Epreuve.objects.create(
            nom="Test Épreuve",
            code="code-test",
            date_debut=now() - timedelta(hours=1),
            date_fin=now() + timedelta(hours=3),
            duree=120,  # minutes
            referent=self.user
        )

    def test_temps_restant_normal(self):
        """
        Vérifie que le temps restant est correct si le début est récent.
        """
        user_epreuve = UserEpreuve.objects.create(
            participant=self.user,
            epreuve=self.epreuve,
            debut_epreuve=now() - timedelta(minutes=30)
        )
        restant = user_epreuve.temps_restant()
        self.assertTrue(5000 < restant <= 5400)  # env. 90 minutes restantes

    def test_temps_restant_termine(self):
        """
        Vérifie que le temps est bien à 0 si dépassé.
        """
        user_epreuve = UserEpreuve.objects.create(
            participant=self.user,
            epreuve=self.epreuve,
            debut_epreuve=now() - timedelta(minutes=130)
        )
        restant = user_epreuve.temps_restant()
        self.assertEqual(restant, 0)

    def test_temps_restant_limite_par_date_fin_globale(self):
        """
        Vérifie que la date de fin de l’épreuve limite bien le temps restant.
        """
        user_epreuve = UserEpreuve.objects.create(
            participant=self.user,
            epreuve=self.epreuve,
            debut_epreuve=now()
        )
        # On raccourcit la date de fin globale
        self.epreuve.date_fin = now() + timedelta(minutes=60)
        self.epreuve.save()

        restant = user_epreuve.temps_restant()
        self.assertTrue(3500 <= restant <= 3700)  # ~1h max au lieu des 2h prévues
