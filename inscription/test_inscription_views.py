from typing import Any

from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from inscription.models import InscripteurExterne, InscriptionExterne, GroupeParticipant
from epreuve.models import Epreuve
from django.utils import timezone
from datetime import timedelta

from intranet.models import ParticipantEstDansGroupe


class InscriptionViewsTests(TestCase):

    def setUp(self):
        # Création d'une épreuve
        self.referent = User.objects.create_user(username="referent", password="mdp")
        maintenant = timezone.now()
        self.epreuve = Epreuve.objects.create(
            nom="TestEpreuve",
            referent=self.referent,
            date_debut=maintenant - timedelta(days=1),
            date_fin=maintenant + timedelta(days=1),
        )

        # Création d’un utilisateur élève
        self.eleve = User.objects.create_user(username="alice", password="mdp")

        # Création de l'inscripteur externe (le prof, pas un utilisateur Django)
        self.inscripteur = InscripteurExterne.objects.create(email="prof@example.com")

        # Inscription externe liée à cette épreuve
        self.inscription_externe = InscriptionExterne.objects.create(
            inscripteur=self.inscripteur,
            epreuve=self.epreuve,
            token="dummy",
            token_est_utilise=True,  # utilisé car déjà exploité pour créer un groupe
            date_creation=timezone.now() - timedelta(hours=1)
        )

        # Création d’un groupe lié à l’inscription
        self.groupe = GroupeParticipant.objects.create(
            nom="groupe-test",
            referent=self.referent,
            inscription_externe=self.inscription_externe,
            statut="VALIDE"
        )

        # L’élève appartient à ce groupe
        ParticipantEstDansGroupe.objects.create(utilisateur=self.eleve, groupe=self.groupe)

    def test_recuperation_compte_envoie_mail(self):
        """
        Vérifie que la récupération de compte fonctionne
        lorsque le username correspond à un utilisateur
        inscrit dans un groupe lié à un inscripteur externe
        avec l’email fourni.
        """
        response = self.client.post(reverse("recuperation_compte"), {
            'username': 'alice',
            'email': 'prof@example.com'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login/confirmation_envoi_lien_reset_password.html")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Réinitialisation", mail.outbox[0].subject)

    def test_reset_password_confirm_view_fonctionne(self) -> None:
        """
        Vérifie le flux complet de réinitialisation du mot de passe via PasswordResetConfirmView.

        Comportement attendu de Django :
        - L'URL contenant le token est "canonicalisée" dès le GET : redirection vers une URL
          où le token est remplacé par 'set-password' (pour éviter l'exposition du token).
        - Le formulaire est ensuite affiché sur l'URL canonicalisée.
        - Le POST doit être fait sur cette URL canonicalisée.
        - À la fin, l'utilisateur est redirigé vers la page de confirmation, et le mot de passe
          est effectivement modifié.
        """
        token: str = default_token_generator.make_token(self.eleve)
        uidb64: str = urlsafe_base64_encode(force_bytes(self.eleve.pk))

        url_avec_token: str = reverse(
            "reset_password_confirm",
            kwargs={"uidb64": uidb64, "token": token},
        )

        # Étape 1 : le GET sur l'URL avec token redirige vers l'URL canonicalisée (.../set-password/)
        response_get_token = self.client.get(url_avec_token)
        self.assertEqual(response_get_token.status_code, 302)

        url_set_password: str = response_get_token["Location"]
        self.assertIn("/set-password/", url_set_password)

        # Étape 2 : le formulaire doit être accessible sur l'URL canonicalisée
        response_get_form = self.client.get(url_set_password)
        self.assertEqual(response_get_form.status_code, 200)
        self.assertTemplateUsed(response_get_form, "login/custom_password_reset_confirm.html")

        # Étape 3 : soumission du nouveau mot de passe sur l'URL canonicalisée
        post_data: dict[str, Any] = {
            "new_password1": "newpass123",
            "new_password2": "newpass123",
        }
        response_post = self.client.post(url_set_password, post_data)
        self.assertEqual(response_post.status_code, 302)

        # Étape 4 : on suit la redirection finale et on vérifie la page "done"
        response_done = self.client.get(response_post["Location"], follow=True)
        self.assertEqual(response_done.status_code, 200)
        self.assertTemplateUsed(response_done, "login/confirmation_modification_mot_de_passe.html")

        # Vérification finale : le mot de passe a bien été persisté en base
        self.eleve.refresh_from_db()
        self.assertTrue(self.eleve.check_password("newpass123"))
