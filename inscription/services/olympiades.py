from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import List, Tuple, Set

from django.contrib.auth.models import User
from django.db import transaction, IntegrityError, connection
from django.db.models import Max, QuerySet
from django.utils import timezone

from epreuve.models import Epreuve
from inscription.models import (
    InscriptionOlympiades,
    InscriptionOlympiadesGroupe, InscriptionAnnales, AnonymatEpreuveEcrite,
)
from intranet.models import GroupeParticipant
from inscription.utils import save_users
from olympiadesnsi import settings


def inscriptions_ouvertes() -> bool:
    """
    Retourne True si on est avant la date limite.
    Si aucune date n'est configurée, on considère que c'est ouvert.
    """
    date_limite = getattr(settings, "OLYMPIADES_DATE_LIMITE_INSCRIPTION", None)
    if date_limite is None:
        return True
    return timezone.now() <= date_limite


def _verrouiller_couple_epreuve_etab(*, epreuve_id: int, etablissement_id: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s);", [epreuve_id, etablissement_id])


# -------------------------------------------------------------------
# Pratique : groupe + users sans mot de passe via ton système existant
# -------------------------------------------------------------------

def _creer_groupe_participant(*, referent: User, nom_groupe: str) -> GroupeParticipant:
    """
    Crée un groupe de participants si nécessaire (sans l'inscrire à une épreuve ici).
    """
    groupe, _ = GroupeParticipant.objects.get_or_create(
        nom=nom_groupe,
        referent=referent,
    )
    return groupe


def _prochain_numero_groupe_pratique(*, inscription: InscriptionOlympiades) -> int:
    """
    Calcule le prochain numéro de groupe pratique (par inscription).
    """
    dernier = (
            InscriptionOlympiadesGroupe.objects
            .filter(inscription=inscription, type_groupe=InscriptionOlympiadesGroupe.TYPE_OLYMPIADES)
            .aggregate(m=Max("numero"))["m"]
            or 0
    )
    return int(dernier) + 1


def _generer_csv_plateforme_depuis_usernames(usernames: List[str]) -> bytes:
    """
    CSV simple (1 username par ligne), cohérent avec ton système (mot de passe choisi à la 1re connexion).
    """
    tampon: io.StringIO = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";")
    ecrivain.writerow(["username"])
    for username in usernames:
        ecrivain.writerow([username])
    return tampon.getvalue().encode("utf-8")


@transaction.atomic
def preparer_groupe_et_comptes_olympiades(
        *,
        epreuve: Epreuve,
        referent: User,
        code_uai: str,
        email_enseignant: str,
        nb_equipes: int,
        inscription: InscriptionOlympiades,
) -> tuple[GroupeParticipant, List[str]]:
    """
    Prépare un groupe pratique et crée nb_equipes comptes élèves (sans mot de passe).

    Retourne :
    - groupe_olympiades
    - usernames créés (pour CSV)
    """
    if nb_equipes <= 0:
        # On crée quand même un groupe ? -> non : ça évite des groupes vides.
        # Les vues peuvent ne pas appeler cette fonction si nb_equipes == 0.
        raise ValueError("nb_equipes doit être > 0")

    numero: int = _prochain_numero_groupe_pratique(inscription=inscription)
    prefixe: str = f"auto-olympiades-{epreuve.id}-{code_uai}-{email_enseignant}-"
    nom_groupe: str = f"{prefixe}{numero:03d}"

    groupe_olympiades: GroupeParticipant = _creer_groupe_participant(
        referent=referent,
        nom_groupe=nom_groupe,
    )

    # Génération des usernames via ton système
    from login.utils import genere_participants_uniques

    usernames: List[str] = genere_participants_uniques(referent, nb_equipes)

    # Création des users + rattachement au groupe + (optionnel) inscription à l'épreuve externe
    # Ici : inscription_externe_id=None, on gère l'inscription à l'épreuve juste après (plus clair)
    res = save_users(groupe_olympiades.id, usernames, inscription_externe_id=None)
    if res.get("status") != "success":
        raise RuntimeError(res.get("message", "Erreur lors de la création des users"))

    # Lien InscriptionOlympiades <-> GroupeParticipant
    _rattacher_groupe_a_inscription(
        inscription=inscription,
        groupe=groupe_olympiades,
        type_groupe=InscriptionOlympiadesGroupe.TYPE_OLYMPIADES,
    )

    return groupe_olympiades, usernames


@transaction.atomic
def inscrire_groupe_olympiades_a_epreuve(*, epreuve: Epreuve, groupe_olympiades: GroupeParticipant) -> None:
    """
    Inscrit le groupe à l'épreuve (écrit/pratique selon ta logique métier).
    """
    epreuve.inscrire_groupe(groupe_olympiades)


# -------------------------------------------------------------------
# Pièces jointes CSV
# -------------------------------------------------------------------

def construire_pieces_jointes_csv(
        *,
        inscription: InscriptionOlympiades,
        usernames_olympiades: List[str],
) -> List[Tuple[str, bytes]]:
    """
    Construit les pièces jointes CSV :
    - écrit : anonymats actifs persistés en base (stable malgré modifications)
    - pratique : usernames (1 par ligne)
    """
    code_uai: str = inscription.code_uai

    csv_ecrit: bytes = generer_csv_epreuve_ecrite_depuis_inscription(inscription=inscription)
    csv_olympiades: bytes = _generer_csv_plateforme_depuis_usernames(usernames_olympiades)

    return [
        (f"{code_uai}_identifiants_epreuve_ecrite.csv", csv_ecrit),
        (f"{code_uai}_identifiants_plateforme_olympiades.csv", csv_olympiades),
    ]


# -------------------------------------------------------------------
# Lien inscription <-> groupe
# -------------------------------------------------------------------

def _rattacher_groupe_a_inscription(
        *,
        inscription: InscriptionOlympiades,
        groupe: GroupeParticipant,
        type_groupe: str,
) -> None:
    """
    Crée la ligne InscriptionOlympiadesGroupe (inscription <-> groupe).

    - ne duplique pas si le lien existe déjà
    - calcule automatiquement le prochain numéro pour (inscription, type_groupe)
    """
    if InscriptionOlympiadesGroupe.objects.filter(inscription=inscription, groupe=groupe).exists():
        return

    dernier_numero = (
            InscriptionOlympiadesGroupe.objects
            .filter(inscription=inscription, type_groupe=type_groupe)
            .aggregate(m=Max("numero"))["m"]
            or 0
    )

    InscriptionOlympiadesGroupe.objects.create(
        inscription=inscription,
        groupe=groupe,
        type_groupe=type_groupe,
        numero=int(dernier_numero) + 1,
    )


def _lister_annales_cibles(*, epreuve_source: Epreuve) -> List[Epreuve]:
    """
    Retourne la liste des épreuves annales à couvrir lors d'une inscription "annales".

    Convention proposée :
        - On considère que l'épreuve source (celle du token) est la "courante"
          (ex: Olympiades 2026).
        - Les annales cibles sont toutes celles renvoyées par epreuve_source.lister_annales()
          (ex: [2025, 2024, 2023, ...]).

    Args:
        epreuve_source: Épreuve associée au token.

    Returns:
        List[Epreuve]: Liste ordonnée des annales (du plus récent au plus ancien, selon ta méthode).
    """
    return list(epreuve_source.lister_annales())


def _inscrire_groupe_a_toutes_les_annales(*, annales: List[Epreuve], groupe: GroupeParticipant) -> None:
    """
    Inscrit réellement un groupe à toutes les annales fournies.

    Important :
        - Utilise Epreuve.inscrire_groupe(), ce qui crée les UserEpreuve/UserExercice
          (et jeux de tests si configurés) comme pour une épreuve normale.
        - On ne suppose pas que l'appel est idempotent, mais ton code côté modèle
          fait déjà un get_or_create sur GroupeParticipeAEpreuve, et bulk_create(ignore_conflicts=True)
          sur UserEpreuve/UserExercice, donc c'est safe.

    Args:
        annales: Liste des annales à inscrire.
        groupe: Groupe à inscrire.
    """
    for annale in annales:
        annale.inscrire_groupe(groupe)


@transaction.atomic
def preparer_groupe_et_comptes_annales(
        *,
        epreuve_source: Epreuve,
        annales_cibles: List[Epreuve],
        referent: User,
        email_enseignant: str,
        nb_equipes: int,
        inscription_annales: InscriptionAnnales,
) -> tuple[GroupeParticipant, List[str]]:
    """
    Crée un groupe + nb_equipes comptes "équipes" et inscrit le groupe à toutes les annales.

    Règles :
        - 1 appel = 1 groupe
        - les comptes créés servent sur l'ensemble des annales (chaîne complète)
        - persistance : on garde le groupe en base et on le rattache à inscription_annales
          (via ton modèle InscriptionAnnales / relation groupes_associes)

    Args:
        epreuve_source: Épreuve associée au token (ex: Olympiades 2026).
        annales_cibles: Liste des annales à couvrir (ex: [2025, 2024, ...]).
        referent: Référent propriétaire du groupe.
        email_enseignant: Email enseignant (issu du token).
        nb_equipes: Nombre d'équipes à générer (> 0).
        inscription_annales: Objet d'inscription annales (unique pour (epreuve_source, email)).

    Returns:
        tuple[GroupeParticipant, List[str]]: (groupe, usernames)

    Raises:
        ValueError: si nb_equipes <= 0.
        RuntimeError: si la création des users échoue.
    """
    if nb_equipes <= 0:
        raise ValueError("nb_equipes doit être > 0")

    # Nom de groupe : on inclut l'épreuve source pour identifier le "paquet annales".
    horodatage: str = timezone.now().strftime("%Y%m%d-%H%M%S")
    nom_groupe: str = f"annales-{epreuve_source.id}-{email_enseignant}-{horodatage}"

    # 1) Création du groupe
    groupe: GroupeParticipant = GroupeParticipant.objects.create(
        nom=nom_groupe,
        referent=referent,
    )

    # 2) Génération usernames (fonction existante)
    from login.utils import genere_participants_uniques

    usernames: List[str] = list(genere_participants_uniques(referent, nb_equipes))

    # 3) Création users + rattachement au groupe
    resultat = save_users(groupe.id, usernames, inscription_externe_id=None)
    if resultat.get("status") != "success":
        raise RuntimeError(resultat.get("message", "Erreur lors de la création des utilisateurs"))

    # 4) Inscription réelle à toutes les annales
    for annale in annales_cibles:
        annale.inscrire_groupe(groupe)

    # 5) Persistance du lien inscription_annales <-> groupe
    # On suppose que nscriptionAnnales a un related_name groupes_associes.
    inscription_annales.groupes_associes.add(groupe)
    return groupe, usernames


@dataclass(frozen=True)
class ComptesResetables:
    """Ensemble des comptes qu'un enseignant peut réinitialiser via son token."""
    users_olympiades: List[User]
    users_annales: List[User]

    @property
    def ids_autorises(self) -> Set[int]:
        ids: Set[int] = set()
        ids.update(u.id for u in self.users_olympiades)
        ids.update(u.id for u in self.users_annales)
        return ids


def _users_du_groupe(groupe: GroupeParticipant) -> QuerySet[User]:
    """
    Retourne les utilisateurs du groupe (QuerySet[User]) via la méthode existante `participants()`.
    On repasse par id__in pour obtenir un QuerySet (utile pour trier/filtrer côté DB).
    """
    ids = [u.id for u in groupe.participants()]
    return User.objects.filter(id__in=ids)


def lister_comptes_resetables(*, epreuve_source: Epreuve, email_enseignant: str) -> ComptesResetables:
    """
    Calcule la liste des comptes que l'enseignant (identifié par email_enseignant + epreuve_source)
    est autorisé à réinitialiser.

    - Olympiades : tous les groupes pratiques rattachés aux inscriptions de ce prof.
    - Annales : tous les groupes rattachés à InscriptionAnnales (epreuve_source + email).

    Returns:
        ComptesResetables: listes triées de User.
    """
    # --- Olympiades (pratique) ---
    inscriptions_olympiades = (
        InscriptionOlympiades.objects
        .filter(epreuve=epreuve_source, email_enseignant=email_enseignant)
        .prefetch_related("groupes_associes__groupe")
    )

    users_olympiades_qs: QuerySet[User] = User.objects.none()
    for ins in inscriptions_olympiades:
        liens = ins.groupes_associes.filter(type_groupe=InscriptionOlympiadesGroupe.TYPE_OLYMPIADES).select_related(
            "groupe")
        for lien in liens:
            users_olympiades_qs = users_olympiades_qs.union(_users_du_groupe(lien.groupe))

    users_olympiades: List[User] = list(users_olympiades_qs.order_by("username"))

    # --- Annales ---
    inscription_annales = (
        InscriptionAnnales.objects
        .filter(epreuve=epreuve_source, email_enseignant=email_enseignant)
        .prefetch_related("groupes_associes")
        .first()
    )

    users_annales_qs: QuerySet[User] = User.objects.none()
    if inscription_annales is not None:
        for groupe in inscription_annales.groupes_associes.all():
            users_annales_qs = users_annales_qs.union(_users_du_groupe(groupe))

    users_annales: List[User] = list(users_annales_qs.order_by("username"))

    return ComptesResetables(users_olympiades=users_olympiades, users_annales=users_annales)


def _anonymats_actifs_de_l_inscription(*, inscription: InscriptionOlympiades) -> QuerySet[AnonymatEpreuveEcrite]:
    return (
        AnonymatEpreuveEcrite.objects
        .filter(inscription=inscription, actif=True)
        .select_for_update()
        .order_by("numero")
    )


def _anonymats_inactifs_reutilisables(*, epreuve: Epreuve, etablissement_id: int) -> QuerySet[AnonymatEpreuveEcrite]:
    """
    Anonymats inactifs existants, réutilisables (réactivation) pour (épreuve, établissement).
    """
    return (
        AnonymatEpreuveEcrite.objects
        .filter(epreuve=epreuve, etablissement_id=etablissement_id, actif=False)
        .filter(numero__gte=1)
        .select_for_update()
        .order_by("-date_modification")
    )


@transaction.atomic
def ajuster_anonymats_epreuve_ecrite(*, inscription: InscriptionOlympiades, nb_voulu: int) -> List[str]:
    """
    Ajuste la liste des anonymats "papier" actifs pour une inscription.

    Règles :
        - Si nb_voulu baisse : on désactive les anonymats actifs "les plus grands" (ou les plus récents).
        - Si nb_voulu augmente : on réactive d'abord des anonymats inactifs réutilisables,
          sinon on alloue de nouveaux numéros libres (1..999).
        - Contrainte forte : jamais de collision sur les anonymats actifs grâce à l'unicité partielle.

    Returns:
        List[str]: liste des identifiants complets (UAI + 3 chiffres) actifs après ajustement, triés.
    """
    if nb_voulu < 0:
        nb_voulu = 0

    epreuve: Epreuve = inscription.epreuve
    etablissement = inscription.etablissement
    code_uai: str = inscription.code_uai
    _verrouiller_couple_epreuve_etab(epreuve_id=epreuve.id, etablissement_id=etablissement.id)

    # Verrouille les actifs de cette inscription (et donc l’état qu’on va modifier)
    anonymats_actifs: List[AnonymatEpreuveEcrite] = list(_anonymats_actifs_de_l_inscription(inscription=inscription))
    nb_actuel: int = len(anonymats_actifs)

    # 1) Baisse : on désactive les "derniers"
    if nb_voulu < nb_actuel:
        a_desactiver = anonymats_actifs[nb_voulu:]  # comme ils sont triés, on coupe la fin
        ids = [a.id for a in a_desactiver]
        if ids:
            AnonymatEpreuveEcrite.objects.filter(id__in=ids).update(actif=False)
        anonymats_actifs = anonymats_actifs[:nb_voulu]
        return [f"{code_uai}{a.numero:03d}" for a in anonymats_actifs]

    # 2) Hausse : il faut en ajouter
    a_ajouter: int = nb_voulu - nb_actuel
    if a_ajouter == 0:
        return [f"{code_uai}{a.numero:03d}" for a in anonymats_actifs]

    # On va avoir besoin des numéros déjà actifs sur (epreuve, etab) pour ne pas boucler inutilement
    numeros_actifs = set(
        AnonymatEpreuveEcrite.objects
        .filter(epreuve=epreuve, etablissement=etablissement, actif=True)
        .values_list("numero", flat=True)
    )

    # 2.a) Réactivation d'inactifs (réutilisation)
    reutilisables = list(_anonymats_inactifs_reutilisables(epreuve=epreuve, etablissement_id=etablissement.id))
    for anonymat in reutilisables:
        if a_ajouter <= 0:
            break
        if anonymat.numero in numeros_actifs:
            continue

        # On tente d'activer : si quelqu’un a activé entre-temps, l’unicité partielle nous protège
        try:
            anonymat.actif = True
            anonymat.inscription = inscription
            anonymat.save(update_fields=["actif", "inscription", "date_modification"])
            numeros_actifs.add(anonymat.numero)
            anonymats_actifs.append(anonymat)
            a_ajouter -= 1
        except IntegrityError:
            # Collision active : on ignore et on passe au suivant
            continue

    # 2.b) Allocation de nouveaux numéros libres (1..999)
    if a_ajouter > 0:
        for numero in range(1, 1000):
            if a_ajouter <= 0:
                break
            if numero in numeros_actifs:
                continue

            # S'il existe déjà une ligne inactive avec ce numéro, on la réactive plutôt que de créer
            existant_inactif = (
                AnonymatEpreuveEcrite.objects
                .filter(epreuve=epreuve, etablissement=etablissement, numero=numero, actif=False)
                .select_for_update()
                .first()
            )

            try:
                if existant_inactif is not None:
                    existant_inactif.actif = True
                    existant_inactif.inscription = inscription
                    existant_inactif.save(update_fields=["actif", "inscription", "date_modification"])
                    anonymat = existant_inactif
                else:
                    anonymat = AnonymatEpreuveEcrite.objects.create(
                        epreuve=epreuve,
                        etablissement=etablissement,
                        numero=numero,
                        actif=True,
                        inscription=inscription,
                    )

                numeros_actifs.add(numero)
                anonymats_actifs.append(anonymat)
                a_ajouter -= 1
            except IntegrityError:
                # Quelqu'un a pris ce numero (actif=True) en parallèle : on continue
                continue

    if a_ajouter > 0:
        raise ValueError(
            f"Impossible d'allouer {nb_voulu} anonymats pour {code_uai} sur {epreuve.nom} : stock 001..999 épuisé."
        )

    anonymats_actifs = sorted(anonymats_actifs, key=lambda a: a.numero)
    return [f"{code_uai}{a.numero:03d}" for a in anonymats_actifs]


def generer_csv_epreuve_ecrite_depuis_inscription(*, inscription: InscriptionOlympiades) -> bytes:
    """
    Export CSV : identifiants écrits (UAI + 3 chiffres) correspondant aux anonymats actifs de l'inscription.
    """
    anonymats = (
        AnonymatEpreuveEcrite.objects
        .filter(inscription=inscription, actif=True)
        .order_by("numero")
    )

    tampon: io.StringIO = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";")
    ecrivain.writerow(["identifiant_ecrit"])

    code_uai: str = inscription.code_uai
    for a in anonymats:
        ecrivain.writerow([f"{code_uai}{a.numero:03d}"])

    return tampon.getvalue().encode("utf-8")
