from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = ('Vérifie si un utilisateur existe, le crée sinon, et met à jour le mot de passe')

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Chemin du fichier csv')

    def handle(self, *args, **options):
        with open(options['csv_path'], "r") as csv_file:
            # Itérer sur chaque ligne du fichier
            for line in csv_file:
                # Ignorer les lignes vides
                if len(line.strip()) == 0:
                    continue

                # Découper la ligne en colonnes
                cols = line.split(";")

                # S'assurer qu'il y a suffisamment de colonnes
                if len(cols) >= 2:
                    username = cols[0].strip()
                    password = cols[1].strip()

                    # Vérifier si l'utilisateur existe
                    user, created = User.objects.get_or_create(username=username)

                    # Mettre à jour le mot de passe, que l'utilisateur soit nouveau ou existant
                    user.set_password(password)
                    user.save()

                    # Afficher un message approprié
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'Utilisateur créé : {username}'))
                    else:
                        self.stdout.write(self.style.SUCCESS(f'Mot de passe mis à jour pour : {username}'))

