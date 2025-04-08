import csv, subprocess, os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from epreuve.models import Epreuve
from django.utils.timezone import now, timedelta


class Command(BaseCommand):
    help = "Crée des utilisateurs de test, les inscrit à une épreuve, lance Locust, puis supprime le CSV"

    def add_arguments(self, parser):
        parser.add_argument('--epreuve_id', type=int, required=True)
        parser.add_argument('--nb', type=int, default=100)
        parser.add_argument('--prefix', type=str, default="testuser")
        parser.add_argument('--password', type=str, default="testpass")
        parser.add_argument('--csv', type=str, default="utilisateurs.csv")

    def handle(self, *args, **options):
        nb = options['nb']
        prefix = options['prefix']
        password = options['password']
        epreuve_id = options['epreuve_id']
        chemin_csv = options['csv']

        epreuve = Epreuve.objects.get(id=epreuve_id)
        if epreuve.pas_commencee():
            epreuve.date_debut = now() - timedelta(minutes=10)
        if epreuve.est_close():
            epreuve.date_fin = now() + timedelta(days=1)
        epreuve.save()

        utilisateurs = []
        for i in range(1, nb + 1):
            username = f"{prefix}{i}"
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(password)
                user.save()
            utilisateurs.append(user)

        epreuve.inscrire_participants(utilisateurs)
        epreuve.assigner_jeux_tests_exercices()

        with open(chemin_csv, "w", newline='') as f:
            writer = csv.writer(f)
            for user in utilisateurs:
                writer.writerow([user.username, password, epreuve.hashid])  # 👈 ici on ajoute le hashid

        self.stdout.write(self.style.SUCCESS(f"{nb} utilisateurs créés et fichier CSV prêt."))

        # Lancer Locust
        try:
            subprocess.run(["locust", "--host=http://127.0.0.1:8000"], check=True)
        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f"Erreur Locust : {e}"))

        # Supprimer le fichier CSV à la fin
        try:
            os.remove(chemin_csv)
            self.stdout.write(self.style.SUCCESS(f"Fichier {chemin_csv} supprimé."))
        except OSError as e:
            self.stderr.write(self.style.WARNING(f"Impossible de supprimer {chemin_csv} : {e}"))
