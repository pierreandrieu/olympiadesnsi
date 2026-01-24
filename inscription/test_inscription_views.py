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
        