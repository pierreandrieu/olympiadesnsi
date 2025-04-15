from typing import List, Optional

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta


class UserEpreuve(models.Model):
    participant = models.ForeignKey(User, related_name='user_epreuves',
                                    on_delete=models.CASCADE)
    epreuve = models.ForeignKey('Epreuve', related_name='participant_entries',
                                on_delete=models.CASCADE)
    debut_epreuve = models.DateTimeField(auto_now=False, null=True)
    anonymat = models.CharField(max_length=255, blank=True, null=True,
                                help_text="Stocke les numéros d'anonymat des 3 participants séparés par '|'.")

    class Meta:
        db_table = 'UserEpreuve'
        indexes = [
            models.Index(fields=['participant', 'epreuve']),
            models.Index(fields=['epreuve', 'participant']),

        ]

        unique_together = ['participant', 'epreuve']

    def set_anonymat(self, anonymats: List[str]) -> None:
        """
        Enregistre les numéros d'anonymat sous la forme d'une chaîne formatée.
        Exemple : ["123", "?", "-"] => "123|?|-"
        """
        self.anonymat = "|".join(anonymats)
        self.save()

    def get_anonymat(self) -> List[str]:
        """
        Récupère les numéros d'anonymat sous forme de liste.
        Retourne ["123", "?", "-"] si l'entrée en BD est "123|?|-"
        """
        return self.anonymat.split("|") if self.anonymat else ["", "", ""]

    def temps_restant(self) -> Optional[int]:
        """
        Calcule le temps restant en secondes pour cet utilisateur à cette épreuve,
        en tenant compte de l'heure de début de l'utilisateur et de la durée de l'épreuve.

        Returns:
            Optional[int]: Temps restant en secondes. Retourne 0 si le temps est écoulé.
        """
        if not self.debut_epreuve or not self.epreuve.duree:
            return None  # Cas inattendu mais possible

        now = timezone.now()

        # Calcul de la fin personnalisée de l'épreuve pour cet utilisateur
        fin_perso = self.debut_epreuve + timedelta(minutes=self.epreuve.duree)

        # On ne dépasse jamais la date de fin globale
        fin_effective = min(fin_perso, self.epreuve.date_fin)

        # Temps restant en secondes
        secondes = (fin_effective - now).total_seconds()

        return max(int(secondes), 0)
