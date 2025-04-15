from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User, Group


class LoginTestCase(TestCase):
    def setUp(self):
        # Création d'un utilisateur et d'un groupe pour les tests_epreuve
        self.username = 'testuser'
        self.password = 'password'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.group = Group.objects.create(name='Participant')
        self.user.groups.add(self.group)
        self.user.save()

    def test_login_success(self):
        # Test de connexion réussie
        response = self.client.post(reverse('login_participant'),
                                    {'username': self.username, 'password': self.password})
        self.assertRedirects(response, reverse('espace_participant'))

    def test_login_failure(self):
        # Test de connexion échouée
        response = self.client.post(reverse('login_participant'),
                                    {'username': self.username, 'password': 'wrongpassword'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', None, 'Identifiant ou mot de passe incorrect.')

