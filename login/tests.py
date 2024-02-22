from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User, Group


class LoginTestCase(TestCase):
    def setUp(self):
        # Création d'un utilisateur et d'un groupe pour les tests
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


class RateLimitTestCase(TestCase):
    def setUp(self):
        """
        Préparation avant chaque test.

        """
        # Création d'un utilisateur et d'un groupe pour les tests
        self.username = 'testuser'
        self.password = 'password'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.group = Group.objects.create(name='Participant')
        self.user.groups.add(self.group)
        self.user.save()

    def test_rate_limit(self):
        """
        Vérification du fonctionnement du rate limit.

        On va bombarder notre serveur de requêtes de connexion pour voir si notre mécanisme de
        limitation de taux bloque bien comme il le devrait après un certain nombre de tentatives.
        C'est un bon moyen de s'assurer que personne ne peut abuser de notre système de connexion.
        """
        # URL cible pour la connexion, changez-la selon l'URL de votre vue de connexion
        url = reverse('login_participant')

        # Infos de connexion, celles de notre utilisateur de test
        login_data = {'username': self.username, 'password': self.password}

        # On envoie plus de requêtes que la limite autorisée pour tester la réaction du système
        for _ in range(10):
            response = self.client.post(url, login_data)
            self.assertEqual(response.status_code, 302)

        response = self.client.post(url, login_data)
        # On s'attend à recevoir un code 403 pour indiquer que la limitation de taux s'applique
        self.assertEqual(response.status_code, 429, "Le système de limitation de taux ne semble pas fonctionner.")
