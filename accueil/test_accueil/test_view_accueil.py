from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from epreuve.models import Epreuve
from datetime import datetime, timedelta
from django.utils.timezone import make_aware


class AccueilViewTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.referent = User.objects.create_user(username="referent", password="test1234")
        self.epreuve_publique = Epreuve.objects.create(
            nom="Épreuve publique",
            code="PUB1",
            date_debut=make_aware(datetime.now() - timedelta(days=1)),
            date_fin=make_aware(datetime.now() + timedelta(days=1)),
            referent=self.referent,
            inscription_externe=True
        )

    def test_home_status_code(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_home_affiche_epreuve_publique(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode()
        self.assertIn("Épreuve publique", content)
        self.assertIn("Nombre d'équipes inscrites", content)

    def test_about_page_status_code(self):
        response = self.client.get(reverse("about"))
        self.assertEqual(response.status_code, 200)
