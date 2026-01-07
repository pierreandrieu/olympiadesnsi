# tests_login_views.py
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core import mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from datetime import timedelta

from inscription.models import InscriptionExterne, InscripteurExterne
from intranet.models import GroupeParticipant, ParticipantEstDansGroupe
from epreuve.models import Epreuve


class LoginViewsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

        self.groupe_participant, _ = Group.objects.get_or_create(name='Participant')
        self.groupe_organisateur, _ = Group.objects.get_or_create(name='Organisateur')

        self.user_participant = User.objects.create_user(username='alice', password='mdp123')
        self.user_participant.groups.add(self.groupe_participant)

        self.user_organisateur = User.objects.create_user(username='bob', password='admin123')
        self.user_organisateur.groups.add(self.groupe_organisateur)

        self.user_sans_password = User.objects.create(username='charlie', is_active=True)
        self.user_inactif = User.objects.create(username='david', is_active=False)

        self.epreuve = Epreuve.objects.create(
            nom="Epreuve test",
            code="000_test",
            date_debut=timezone.now(),
            date_fin=timezone.now() + timedelta(hours=2),
            duree=90,
            referent=self.user_organisateur
        )

        # Crée un inscripteur externe à partir de l’email du user_organisateur
        self.inscripteur_externe = InscripteurExterne.objects.create(
            email=self.user_organisateur.email
        )

        # Associe ensuite cet inscripteur externe à une inscription
        self.inscription_externe = InscriptionExterne.objects.create(
            epreuve=self.epreuve,
            inscripteur=self.inscripteur_externe
        )


        self.groupe = GroupeParticipant.objects.create(
            nom="Groupe 1", referent=self.user_organisateur, inscription_externe=self.inscription_externe
        )
        ParticipantEstDansGroupe.objects.create(utilisateur=self.user_participant, groupe=self.groupe)

    def test_connexion_participant_succes(self):
        response = self.client.post(reverse("login_participant"), {
            'username': 'alice', 'password': 'mdp123'
        })
        self.assertRedirects(response, reverse("espace_participant"))

    def test_connexion_organisateur_succes(self):
        response = self.client.post(reverse("login_organisateur"), {
            'username': 'bob', 'password': 'admin123'
        })
        self.assertRedirects(response, reverse("espace_organisateur"))

    def test_connexion_echec_mauvais_password(self):
        response = self.client.post(reverse("login_participant"), {
            'username': 'alice', 'password': 'wrong'
        })
        self.assertContains(response, "Identifiant ou mot de passe incorrect.")

    def test_connexion_echec_mauvais_groupe(self):
        response = self.client.post(reverse("login_organisateur"), {
            'username': 'alice', 'password': 'mdp123'
        })
        self.assertContains(response, "Identifiant ou mot de passe incorrect.")

    def test_prelogin_redirige_vers_set_password(self):
        response = self.client.post(reverse("prelogin"), {'username': 'charlie'})
        self.assertRedirects(response, reverse("set_password", kwargs={'username': 'charlie'}))

    def test_prelogin_redirige_vers_login_participant(self):
        response = self.client.post(reverse("prelogin"), {'username': 'alice'})
        self.assertRedirects(response, reverse("login_participant"))

    def test_set_password_valide(self):
        response = self.client.post(reverse("set_password", kwargs={'username': 'charlie'}), {
            'new_password1': 'testpass123',
            'new_password2': 'testpass123'
        })
        self.assertRedirects(response, reverse("login_participant"))
        self.user_sans_password.refresh_from_db()
        self.assertTrue(self.user_sans_password.has_usable_password())

class LoginTestCase(TestCase):
    def setUp(self):
        cache.clear()

        # Création d'un utilisateur et d'un groupe pour les tests_epreuve
        self.username = 'testuser'
        self.password = 'password'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.group, _ = Group.objects.get_or_create(name='Participant')
        self.user.groups.add(self.group)
        self.user.save()

    def test_login_success(self):
        # Test de connexion réussie
        response = self.client.post(reverse('login_participant'),
                                    {'username': self.username, 'password': self.password})
        self.assertRedirects(response, reverse('espace_participant'))

    def test_login_failure(self):
        response = self.client.post(
            reverse('login_participant'),
            {'username': self.username, 'password': 'wrongpassword'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identifiant ou mot de passe incorrect.")
