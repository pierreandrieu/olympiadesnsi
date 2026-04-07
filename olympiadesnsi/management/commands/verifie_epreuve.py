# management/commands/verifie_epreuve.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from epreuve.models import Epreuve
from epreuve.models.userexercice import UserExercice
from epreuve.models.userepreuve import UserEpreuve


class Command(BaseCommand):
    """
    Vérifie la cohérence d'une épreuve :

    - Liste les exercices avec :
        * id
        * nom
        * avec_jeu_de_test
        * nombre de jeux de test disponibles

    - Liste les participants avec :
        * username
        * date de début

    - Pour chaque participant et chaque exercice :
        * '-' si pas de jeu de test
        * id du jeu de test sinon
        * signale les cas où un jeu de test est attendu mais absent

    Usage :
        python manage.py verifie_epreuve <id_epreuve>
    """

    def add_arguments(self, parser):
        parser.add_argument("epreuve_id", type=int)

    def handle(self, *args, **options):
        epreuve_id = options["epreuve_id"]

        try:
            epreuve = Epreuve.objects.get(id=epreuve_id)
        except Epreuve.DoesNotExist:
            self.stdout.write(self.style.ERROR("Épreuve introuvable"))
            return

        self.stdout.write(f"\n=== Épreuve : {epreuve.nom} (id={epreuve.id}) ===\n")

        exercices = list(epreuve.get_exercices().order_by("numero"))

        # ------------------------------------------------------------------
        # 1. Infos exercices
        # ------------------------------------------------------------------
        self.stdout.write("=== Exercices ===")
        for exo in exercices:
            nb_jeux = exo.get_jeux_de_test().count()
            self.stdout.write(
                f"[{exo.id}] {exo.titre} | jeu_de_test={exo.avec_jeu_de_test} | nb_jeux={nb_jeux}"
            )

        # ------------------------------------------------------------------
        # 2. Participants
        # ------------------------------------------------------------------
        self.stdout.write("\n=== Participants ===")

        user_epreuves = (
            UserEpreuve.objects
            .filter(epreuve=epreuve)
            .select_related("participant")
        )

        participants = list(user_epreuves)

        for ue in participants:
            date_debut = ue.debut_epreuve or "-"
            self.stdout.write(f"{ue.participant.username} | debut={date_debut}")

        # ------------------------------------------------------------------
        # 3. Vérification des jeux de test
        # ------------------------------------------------------------------
        self.stdout.write("\n=== Détail par participant ===")

        problemes = []

        for ue in participants:
            user = ue.participant
            self.stdout.write(f"\n--- {user.username} ---")

            for exo in exercices:
                try:
                    uex = UserExercice.objects.get(participant=user, exercice=exo)
                except UserExercice.DoesNotExist:
                    problemes.append(
                        f"{user.username} n'a pas de UserExercice pour exo {exo.id}"
                    )
                    self.stdout.write(f"{exo.id}: ❌ absent")
                    continue

                if not exo.avec_jeu_de_test:
                    self.stdout.write(f"{exo.id}: -")
                    continue

                if uex.jeu_de_test:
                    self.stdout.write(f"{exo.id}: {uex.jeu_de_test.id}")
                else:
                    self.stdout.write(f"{exo.id}: ❌ PAS DE JEU DE TEST")
                    problemes.append(
                        f"{user.username} / exo {exo.id} sans jeu de test"
                    )

        # ------------------------------------------------------------------
        # 4. Résumé problèmes
        # ------------------------------------------------------------------
        self.stdout.write("\n=== Problèmes détectés ===")

        if not problemes:
            self.stdout.write(self.style.SUCCESS("Aucun problème détecté ✅"))
        else:
            for p in problemes:
                self.stdout.write(self.style.ERROR(p))

            self.stdout.write(
                self.style.ERROR(f"\nTotal problèmes : {len(problemes)} ❌")
            )