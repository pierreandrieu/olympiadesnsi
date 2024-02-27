from django.db import models
from django.contrib.auth.models import User, Group
# from inscription.models import Inscripteur
import olympiadesnsi.constants as constantes


class GroupeParticipant(models.Model):
    def get_nombre_participants(self) -> int:
        """
        Renvoie le nombre de participants dans le groupe.

        :return: Le nombre de participants dans le groupe.
        """
        return self.membres.count()  # Utilise la relation inverse `membres` définie dans ParticipantEstDansGroupe

    def participants(self):
        """
        Renvoie tous les utilisateurs membres du groupe.

        :return: QuerySet des utilisateurs membres du groupe.
        """
        return User.objects.filter(appartenances__groupe=self)

    STATUT_CHOICES = (
        ('VALIDE', 'Valide'),
        ('CREATION', 'En cours de création'),
        ('ECHEC', 'Échec'),
    )

    nom = models.CharField(max_length=constantes.MAX_TAILLE_NOM, verbose_name="Nom du groupe")
    referent = models.ForeignKey(User, related_name='groupes_administres', on_delete=models.CASCADE,
                                 verbose_name="Référent")
    date_creation = models.DateField(auto_now_add=True, verbose_name="Date de création")
    inscripteur = models.ForeignKey("inscription.InscripteurExterne", related_name="inscripteur_groupe",
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True, verbose_name="Inscripteur")
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='CREATION', verbose_name="Statut")

    def __str__(self):
        return f"{self.nom} (Référent : {self.referent.username})"

    class Meta:
        db_table = 'GroupeParticipant'
        indexes = [
            models.Index(fields=['referent', 'nom']),
        ]
        unique_together = [('referent', 'nom')]
        verbose_name = "groupe de participants"
        verbose_name_plural = "groupes de participants"


class ParticipantEstDansGroupe(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appartenances')
    groupe = models.ForeignKey(GroupeParticipant, on_delete=models.CASCADE, related_name='membres')
    date_ajout = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('utilisateur', 'groupe')
        db_table = 'Participant_EstDansGroupe'
        verbose_name = 'appartenance de groupe'
        verbose_name_plural = 'appartenances de groupe'

    def __str__(self):
        return f"{self.utilisateur.username} est dans {self.groupe.nom} cree par {self.groupe.referent.username}"
