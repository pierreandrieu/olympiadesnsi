from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from epreuve.models import Epreuve, UserEpreuve, UserExercice, GroupeParticipeAEpreuve


class Command(BaseCommand):
    help = 'Vérifie et assure l\'intégrité des entrées UserEpreuve et UserExercice dans la base de données'

    def handle(self, *args, **kwargs):
        self.stdout.write("Début de la vérification de l'intégrité de la base de données...")

        for epreuve in Epreuve.objects.all():
            groupes_participants = GroupeParticipeAEpreuve.objects.filter(epreuve=epreuve)

            for groupe_participant in groupes_participants:
                utilisateurs = User.objects.filter(groups=groupe_participant.groupe)

                for utilisateur in utilisateurs:
                    # Créer UserEpreuve si nécessaire, sans écraser fin_epreuve
                    user_epreuve, created = UserEpreuve.objects.get_or_create(
                        participant=utilisateur,
                        epreuve=epreuve
                    )

                    # Pour chaque exercice de l'épreuve
                    for exercice in epreuve.exercice_set.all():
                        # Créer UserExercice si nécessaire
                        UserExercice.objects.get_or_create(
                            participant=utilisateur,
                            exercice=exercice
                        )

        self.stdout.write(self.style.SUCCESS('Vérification terminée avec succès.'))
