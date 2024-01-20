from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group


class Command(BaseCommand):
    help = ('Ajoute une epreuve avec trois exercices et un participant')

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='chemin du fichier csv')

    def handle(self, *args, **options):
        # Configuration
        groupe_participant, _ = Group.objects.get_or_create(name="auto_created")
        with open(options['csv_path'], "r") as csv_participants:
            # Itérer sur chaque ligne du fichier
            for line in csv_participants:
                # Ignorer les lignes vides
                if len(line.strip()) == 0:
                    continue

                # Découper la ligne en colonnes
                cols = line.split(";")

                # S'assurer qu'il y a suffisamment de colonnes
                if len(cols) >= 2:
                    username = cols[0]
                    password = cols[1][:-1]
                    print(username, password, len(password))
                    user, created = User.objects.get_or_create(username=username)
                    if created:
                        user.set_password(password)
                        user.save()
                        groupe_participant.user_set.add(user)

        self.stdout.write(self.style.SUCCESS('Participant créé avec succès'))
