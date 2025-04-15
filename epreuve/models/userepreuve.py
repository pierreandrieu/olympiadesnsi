from typing import List, TYPE_CHECKING

from django.contrib.auth.models import User
from django.db import models

if TYPE_CHECKING:
    from epreuve.models.epreuve import Epreuve


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
