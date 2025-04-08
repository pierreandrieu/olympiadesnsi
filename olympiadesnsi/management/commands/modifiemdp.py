from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group


class Command(BaseCommand):
    help = ('Modifie les mots de passe des utilisateurs du fichier csv a deux colonnes : nom et mot de passe')

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='chemin du fichier csv')

    def handle(self, *args, **options):
        # Configuration
        with open(options['csv_path'], "r") as csv_organisateurs:
            # Itérer sur chaque ligne du fichier
            for line in csv_organisateurs:
                # Ignorer les lignes vides
                if len(line.strip()) == 0:
                    continue

                # Découper la ligne en colonnes
                cols = line.split(";")

                # S'assurer qu'il y a suffisamment de colonnes
                if len(cols) >= 2:
                    username = cols[0]
                    password = cols[1].strip()
                    user, created = User.objects.get_or_create(username=username)
                    if not created:
                        user.set_password(password)
                        user.save()
                        self.stdout.write(self.style.SUCCESS(f'Mot de passe de {username} modifié avec succès'))
