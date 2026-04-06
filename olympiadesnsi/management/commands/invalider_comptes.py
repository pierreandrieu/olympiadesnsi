# management/commands/renommer_comptes_batch.py

# python manage.py renommer_comptes_batch comptes_a_invalider.txt
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from intranet.models import ParticipantEstDansGroupe
from login.utils import genere_participants_uniques

from datetime import datetime


class Command(BaseCommand):
    help = "Renomme en masse des comptes compromis à partir d'un fichier"

    def add_arguments(self, parser):
        parser.add_argument("fichier", type=str)

    def handle(self, *args, **options):
        chemin_fichier = options["fichier"]

        # 1. Lecture fichier
        try:
            with open(chemin_fichier, "r") as f:
                usernames = [ligne.strip() for ligne in f if ligne.strip()]
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("Fichier introuvable"))
            return

        if not usernames:
            self.stdout.write(self.style.ERROR("Fichier vide"))
            return

        # 2. Récupération users
        users = list(User.objects.filter(username__in=usernames))

        if len(users) != len(usernames):
            usernames_trouves = {u.username for u in users}
            manquants = [u for u in usernames if u not in usernames_trouves]

            self.stdout.write(self.style.ERROR("Utilisateurs introuvables :"))
            for u in manquants:
                self.stdout.write(f"  - {u}")
            return

        # 3. Vérification référent unique
        referents = set()
        user_to_referent = {}

        for user in users:
            appartenance = (
                ParticipantEstDansGroupe.objects
                .select_related("groupe__referent")
                .filter(utilisateur=user)
                .first()
            )

            if not appartenance:
                self.stdout.write(self.style.ERROR(
                    f"Utilisateur sans groupe : {user.username}"
                ))
                return

            referent = appartenance.groupe.referent
            if not referent:
                self.stdout.write(self.style.ERROR(
                    f"Pas de référent pour : {user.username}"
                ))
                return

            referents.add(referent.id)
            user_to_referent[user] = referent

        if len(referents) != 1:
            self.stdout.write(self.style.ERROR(
                "❌ Plusieurs référents détectés, opération annulée"
            ))
            return

        referent = next(iter(user_to_referent.values()))

        # 4. Résumé
        self.stdout.write("\n--- Résumé ---")
        self.stdout.write(f"Nombre de comptes : {len(users)}")
        self.stdout.write(f"Référent unique   : {referent.username} (id={referent.id})")

        self.stdout.write("\nComptes concernés :")
        for user in users:
            self.stdout.write(f"  - {user.username}")

        # 5. Confirmation
        self.stdout.write("\n⚠️ Cette action va :")
        self.stdout.write("- changer tous les usernames")
        self.stdout.write("- invalider tous les mots de passe\n")

        confirmation = input("Confirmer ? (oui/non) : ").strip().lower()

        if confirmation not in ["oui", "o", "yes", "y"]:
            self.stdout.write(self.style.WARNING("❌ Opération annulée"))
            return

        # 6. Génération nouveaux usernames
        nouveaux_usernames = genere_participants_uniques(referent, len(users))

        # 7. Création fichier log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nom_fichier_log = f"maj_comptes_{timestamp}.txt"

        lignes_log = []
        lignes_log.append(f"Date : {timestamp}")
        lignes_log.append(f"Référent : {referent.username}")
        lignes_log.append("")

        # 8. Application
        self.stdout.write("\n--- Résultat ---")

        for user, new_username in zip(users, nouveaux_usernames):
            ancien = user.username

            user.username = new_username
            user.set_unusable_password()
            user.save(update_fields=["username", "password"])

            ligne = f"{ancien} → {new_username}"
            lignes_log.append(ligne)

            self.stdout.write(ligne)

        # 9. Écriture du fichier
        with open(nom_fichier_log, "w") as f:
            f.write("\n".join(lignes_log))

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Tous les comptes ont été mis à jour"
        ))
        self.stdout.write(f"📄 Fichier log : {nom_fichier_log}")
