from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from django.contrib.auth.models import User
from epreuve.models import Epreuve
from epreuve.utils import get_cache_key_liste_epreuves_publiques


class EpreuveModelTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create(username="testuser")

    def _create_epreuve(self, nom="Test Epreuve", inscription_externe=False):
        now = timezone.now()
        return Epreuve.objects.create(
            nom=nom,
            code="",
            date_debut=now,
            date_fin=now + timedelta(hours=1),
            referent=self.user,
            inscription_externe=inscription_externe
        )

    def test_code_auto_genere(self):
        epreuve = self._create_epreuve("Nom Cool")
        self.assertTrue(epreuve.code.startswith(f"{epreuve.id:03d}_nom-cool"))

    def test_str_renvoie_nom(self):
        epreuve = self._create_epreuve("Mon Épreuve")
        self.assertEqual(str(epreuve), "Mon Épreuve")

    def test_est_close_et_pas_commencee(self):
        now = timezone.now()
        future = Epreuve.objects.create(
            nom="Futur", code="", date_debut=now + timedelta(days=1),
            date_fin=now + timedelta(days=2), referent=self.user
        )
        past = Epreuve.objects.create(
            nom="Passée", code="", date_debut=now - timedelta(days=2),
            date_fin=now - timedelta(days=1), referent=self.user
        )
        self.assertTrue(future.pas_commencee())
        self.assertFalse(future.est_close())
        self.assertTrue(past.est_close())
        self.assertFalse(past.pas_commencee())

    def test_liste_epreuves_publiques(self):
        self._create_epreuve("Publique", inscription_externe=True)
        self._create_epreuve("Privée", inscription_externe=False)
        publiques = Epreuve.liste_epreuves_publiques()
        self.assertEqual(len(publiques), 1)
        self.assertEqual(publiques[0].nom, "Publique")

    def test_cache_compte_participants_inscrits(self):
        epreuve = self._create_epreuve()
        key = f"epreuve_{epreuve.id}_nombre_participants"
        cache.set(key, 42)
        self.assertEqual(epreuve.compte_participants_inscrits(), 42)
        cache.delete(key)

    def test_cache_recalcule_si_absent(self):
        epreuve = self._create_epreuve()
        key = f"epreuve_{epreuve.id}_nombre_participants"
        cache.delete(key)
        self.assertEqual(epreuve.compte_participants_inscrits(), 0)
        self.assertEqual(cache.get(key), 0)

    def test_maj_cache_nb_participants(self):
        epreuve = self._create_epreuve()
        key = f"epreuve_{epreuve.id}_nombre_participants"
        cache.set(key, 5)
        epreuve._maj_cache_nb_participants_epreuve(3)
        self.assertEqual(cache.get(key), 8)
        epreuve._maj_cache_nb_participants_epreuve(-2)
        self.assertEqual(cache.get(key), 6)

    def test_maj_cache_recalcule_si_absent(self):
        epreuve = self._create_epreuve()
        cache.delete(f"epreuve_{epreuve.id}_nombre_participants")
        epreuve._maj_cache_nb_participants_epreuve(0)
        self.assertEqual(cache.get(f"epreuve_{epreuve.id}_nombre_participants"), 0)


class AccueilViewTests(TestCase):
    def setUp(self):
        cache.clear()

        self.user = User.objects.create(username="viewuser")
        self.epreuve_publique = Epreuve.objects.create(
            nom="Visible", code="", date_debut=timezone.now(),
            date_fin=timezone.now() + timedelta(hours=1),
            referent=self.user, inscription_externe=True
        )

    def test_accueil_vue_affiche_epreuve(self):
        client = Client()
        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible")


class EpreuveCacheTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="cacheuser")

    def test_cache_est_vide_par_defaut(self):
        self.assertIsNone(cache.get(get_cache_key_liste_epreuves_publiques()))

    def test_epreuve_publique_invalide_le_cache(self):
        # Remplir manuellement le cache
        cache.set(get_cache_key_liste_epreuves_publiques(), "DUMMY")
        self.assertEqual(cache.get(get_cache_key_liste_epreuves_publiques()), "DUMMY")

        # Créer une épreuve publique
        epreuve = Epreuve.objects.create(
            nom="Test publique",
            code="",
            date_debut=timezone.now(),
            date_fin=timezone.now() + timedelta(hours=1),
            referent=self.user,
            inscription_externe=True
        )

        # Vérifie si le cache a été invalidé
        self.assertIsNone(cache.get(get_cache_key_liste_epreuves_publiques()))

    def test_epreuve_non_publique_ne_touche_pas_au_cache(self):
        cache.set(get_cache_key_liste_epreuves_publiques(), "KEEP_ME")

        Epreuve.objects.create(
            nom="Test privée",
            code="",
            date_debut=timezone.now(),
            date_fin=timezone.now() + timedelta(hours=1),
            referent=self.user,
            inscription_externe=False
        )

        self.assertEqual(cache.get(get_cache_key_liste_epreuves_publiques()), "KEEP_ME")

    def tearDown(self):
        cache.clear()

    from django.urls import reverse

class EpreuveModificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="owner", password="test1234")
        self.autre_user = User.objects.create_user(username="intrus", password="test1234")
        self.epreuve = Epreuve.objects.create(
            nom="À modifier",
            code="",
            date_debut=timezone.now(),
            date_fin=timezone.now() + timedelta(hours=1),
            referent=self.user,
            inscription_externe=False
        )

    def test_modification_nom_met_a_jour_code(self):
        self.epreuve.nom = "Nom changé"
        self.epreuve.save()
        self.epreuve.refresh_from_db()
        self.assertTrue(self.epreuve.code.startswith(f"{self.epreuve.id:03d}_nom-change"))

    def test_vue_editer_epreuve_get_accessible_par_referent(self):
        client = Client()
        client.force_login(self.user)
        url = reverse("editer_epreuve", args=[self.epreuve.id])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "À modifier")

    def test_vue_editer_epreuve_post_modifie_nom(self):
        client = Client()
        client.force_login(self.user)
        url = reverse("editer_epreuve", args=[self.epreuve.id])
        response = client.post(url, {
            "nom": "Nom mis à jour",
            "date_debut": self.epreuve.date_debut,
            "date_fin": self.epreuve.date_fin,
            "referent": self.user.id,
            "inscription_externe": self.epreuve.inscription_externe,
        })
        self.assertRedirects(response, reverse("afficher_epreuve", args=[self.epreuve.id]))
        self.epreuve.refresh_from_db()
        self.assertEqual(self.epreuve.nom, "Nom mis à jour")

    def test_vue_editer_epreuve_interdite_pour_non_referent(self):
        client = Client()
        client.force_login(self.autre_user)
        url = reverse("editer_epreuve", args=[self.epreuve.id])
        response = client.get(url)
        self.assertIn(response.status_code, [302, 403])  # selon ton décorateur ou mixin utilisé
