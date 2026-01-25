from __future__ import annotations

from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import QuerySet

from epreuve.models import Epreuve


def _chaine_annales(epreuve: Epreuve, limite: int = 20) -> str:
    """
    Construit une représentation lisible de la chaîne d'annales.
    Exemple: "2026 -> 2025 -> 2024"
    """
    noms = [f"{epreuve.id}:{epreuve.nom}"]
    courant = epreuve.annale
    i = 0
    while courant is not None and i < limite:
        noms.append(f"{courant.id}:{courant.nom}")
        courant = courant.annale
        i += 1
    if courant is not None:
        noms.append("... (limite atteinte)")
    return " -> ".join(noms)


def _verifier_pas_de_cycle(epreuve_courante: Epreuve, annale: Epreuve) -> None:
    """
    Vérifie que définir epreuve_courante.annale = annale ne crée pas de cycle.
    """
    courant = annale
    vus = set()
    while courant is not None:
        if courant.id == epreuve_courante.id:
            raise CommandError("Cycle détecté : ce lien créerait une boucle d'annales.")
        if courant.id in vus:
            # Sécurité (cas de base déjà corrompue)
            raise CommandError("Cycle détecté dans la chaîne existante (base incohérente).")
        vus.add(courant.id)
        courant = courant.annale


class Command(BaseCommand):
    help = "Lister des épreuves (filtre texte) et lier/délier le champ annale entre épreuves."

    def add_arguments(self, parser):
        parser.add_argument(
            "--motif",
            type=str,
            default="olympiades",
            help="Motif recherché dans le nom (icontains). Défaut : 'olympiades'.",
        )
        parser.add_argument(
            "--lister",
            action="store_true",
            help="Liste les épreuves correspondant au motif (id, nom, référent, annale...).",
        )

        # Important : selon ton besoin, on veut que X soit l'annale de Y => on écrit Y.annale = X
        parser.add_argument(
            "--lier",
            nargs=2,
            type=int,
            metavar=("ANNALE_ID", "EPREUVE_ID"),
            help="Déclare que l'épreuve EPREUVE_ID a pour annale ANNALE_ID (EPREUVE_ID.annale = ANNALE_ID).",
        )

        parser.add_argument(
            "--delier",
            type=int,
            metavar="EPREUVE_ID",
            help="Supprime le lien annale de l'épreuve EPREUVE_ID (EPREUVE_ID.annale = NULL).",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche ce qui serait fait sans écrire en base (utile avec --lier / --delier).",
        )

    def handle(self, *args, **options):
        motif: str = options["motif"]
        faire_liste: bool = options["lister"]
        lier = options.get("lier")
        delier: Optional[int] = options.get("delier")
        dry_run: bool = options["dry_run"]

        if not faire_liste and not lier and not delier:
            self.stdout.write("Rien à faire. Utilise --lister, --lier ou --delier.")
            return

        if faire_liste:
            self._lister_epreuves(motif)

        if lier:
            annale_id, epreuve_id = lier
            self._lier(annale_id=annale_id, epreuve_id=epreuve_id, dry_run=dry_run)

        if delier is not None:
            self._delier(epreuve_id=delier, dry_run=dry_run)

    def _lister_epreuves(self, motif: str) -> None:
        qs: QuerySet[Epreuve] = (
            Epreuve.objects
            .filter(nom__icontains=motif)
            .select_related("referent", "annale")
            .order_by("id")
        )

        if not qs.exists():
            self.stdout.write(f"Aucune épreuve trouvée avec motif '{motif}'.")
            return

        self.stdout.write(f"Épreuves dont le nom contient '{motif}' :")
        for e in qs:
            referent = getattr(e.referent, "username", str(e.referent_id))
            annale_txt = f"{e.annale_id}:{e.annale.nom}" if e.annale else "—"
            self.stdout.write(f"- ID {e.id} | {e.nom} | référent={referent} | annale={annale_txt}")

        self.stdout.write("\nChaînes d'annales (aperçu) :")
        for e in qs:
            self.stdout.write(f"  {_chaine_annales(e)}")

    @transaction.atomic
    def _lier(self, annale_id: int, epreuve_id: int, dry_run: bool) -> None:
        if annale_id == epreuve_id:
            raise CommandError("Impossible : ANNALE_ID et EPREUVE_ID sont identiques.")

        try:
            annale = Epreuve.objects.get(id=annale_id)
        except Epreuve.DoesNotExist:
            raise CommandError(f"Annale introuvable (id={annale_id}).")

        try:
            epreuve = Epreuve.objects.get(id=epreuve_id)
        except Epreuve.DoesNotExist:
            raise CommandError(f"Épreuve introuvable (id={epreuve_id}).")

        # Vérifie qu'on ne crée pas de cycle
        _verifier_pas_de_cycle(epreuve_courante=epreuve, annale=annale)

        ancien = epreuve.annale
        self.stdout.write("Lien demandé :")
        self.stdout.write(f"  - Épreuve : {epreuve.id} - {epreuve.nom}")
        self.stdout.write(f"  - Annale  : {annale.id} - {annale.nom}")
        if ancien:
            self.stdout.write(f"  - Ancienne annale : {ancien.id} - {ancien.nom}")

        if dry_run:
            self.stdout.write("DRY-RUN : aucune écriture en base.")
            return

        epreuve.annale = annale
        epreuve.save(update_fields=["annale"])
        self.stdout.write("✔ Lien enregistré.")
        self.stdout.write(f"Chaîne : {_chaine_annales(epreuve)}")

    @transaction.atomic
    def _delier(self, epreuve_id: int, dry_run: bool) -> None:
        try:
            epreuve = Epreuve.objects.select_related("annale").get(id=epreuve_id)
        except Epreuve.DoesNotExist:
            raise CommandError(f"Épreuve introuvable (id={epreuve_id}).")

        if epreuve.annale is None:
            self.stdout.write("Rien à faire : l'épreuve n'a pas d'annale.")
            return

        self.stdout.write("Déliaison demandée :")
        self.stdout.write(f"  - Épreuve : {epreuve.id} - {epreuve.nom}")
        self.stdout.write(f"  - Annale  : {epreuve.annale.id} - {epreuve.annale.nom}")

        if dry_run:
            self.stdout.write("DRY-RUN : aucune écriture en base.")
            return

        epreuve.annale = None
        epreuve.save(update_fields=["annale"])
        self.stdout.write("✔ Lien supprimé.")
