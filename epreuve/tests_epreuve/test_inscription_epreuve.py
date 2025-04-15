from django.test import TestCase
from django.contrib.auth.models import User
from epreuve.models import Epreuve
from inscription.models import GroupeParticipant, GroupeParticipeAEpreuve
from django.utils.timezone import now
from datetime import timedelta

from intranet.models import ParticipantEstDansGroupe


class EpreuveInscritsTests(TestCase):

    def setUp(self):
        self.referent = User.objects.create_user(username="referent")
        self.participant1 = User.objects.create_user(username="participant1")
        self.participant2 = User.objects.create_user(username="participant2")
        self.non_inscrit = User.objects.create_user(username="intrus")

        self.epreuve = Epreuve.objects.create(
            nom="Test",
            code="",
            date_debut=now(),
            date_fin=now() + timedelta(hours=1),
            referent=self.referent
        )

        self.groupe = GroupeParticipant.objects.create(
            nom="Groupe Test",
            referent=self.referent
        )

        GroupeParticipeAEpreuve.objects.create(groupe=self.groupe, epreuve=self.epreuve)

        ParticipantEstDansGroupe.objects.create(utilisateur=self.participant1, groupe=self.groupe)
        ParticipantEstDansGroupe.objects.create(utilisateur=self.participant2, groupe=self.groupe)

    def test_inscrits_retourne_utilisateurs_du_groupe(self):
        inscrits = self.epreuve.inscrits

        self.assertEqual(inscrits.count(), 2)
        self.assertIn(self.participant1, inscrits)
        self.assertIn(self.participant2, inscrits)
        self.assertNotIn(self.non_inscrit, inscrits)
