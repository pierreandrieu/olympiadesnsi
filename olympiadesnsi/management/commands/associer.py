from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from epreuve.models import Epreuve


class Command(BaseCommand):
    help = "Lister les épreuves d'un référent ou lier une épreuve à une annale"

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help="Nom d'utilisateur (username) du référent pour lister ses épreuves"
        )
        parser.add_argument(
            '--lier',
            nargs=2,
            type=int,
            metavar=('EPREUVE_ID', 'ANNALE_ID'),
            help="Associer une épreuve à une annale via leurs ID"
        )

        parser.add_argument(
            '--delier',
            nargs=1,
            type=int,
            metavar=('EPREUVE_ID'),
            help="Désassocier une épreuve de son annale via son ID"
        )

    def handle(self, *args, **options):
        username = options.get('username')
        lier = options.get('lier')
        delier = options.get('delier')

        if username:
            try:
                referent = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stderr.write(f"Utilisateur {username} introuvable.")
                return

            epreuves = Epreuve.objects.filter(referent=referent).order_by('id')
            if not epreuves.exists():
                self.stdout.write(f"Aucune épreuve trouvée pour {username}")
                return

            self.stdout.write(f"Épreuves du référent {username} :")
            for e in epreuves:
                ligne = f" - ID {e.id} : {e.nom}"
                if e.annale:
                    ligne += f" (annale : {e.annale.nom})"
                self.stdout.write(ligne)

        if lier:
            epreuve_id, annale_id = lier
            try:
                epreuve = Epreuve.objects.get(id=epreuve_id)
                annale = Epreuve.objects.get(id=annale_id)
            except Epreuve.DoesNotExist as e:
                self.stderr.write(f"Erreur : {e}")
                return

            epreuve.annale = annale
            epreuve.save()
            self.stdout.write(
                f"✔️ L'épreuve « {epreuve.nom} » (ID {epreuve.id}) pointe maintenant vers l’annale « {annale.nom} » (ID {annale.id})")

        if delier:
            epreuve_id, = delier
            try:
                epreuve = Epreuve.objects.get(id=epreuve_id)
            except Epreuve.DoesNotExist as e:
                self.stderr.write(f"Erreur : {e}")
                return

            epreuve.annale = None
            epreuve.save()
            self.stdout.write(
                f"✔️ L'épreuve « {epreuve.nom} » (ID {epreuve.id}) ne pointe plus vers d'annale.")
        if not username and not lier and not delier:
            self.stdout.write("Aucun argument fourni. Utilisez --username, --lier ou --delier.")
