from __future__ import annotations

import csv
import io
from typing import List, Tuple

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from epreuve.models import Epreuve
from inscription.models import (
    GroupeParticipant,
    InscriptionOlympiades,
    InscriptionOlympiadesGroupe, InscriptionAnnales,
)
from inscription.utils import save_users


# -------------------------------------------------------------------
# Écrit : identifiants UAI + 3 chiffres, sans collision entre profs
# -------------------------------------------------------------------

def _compter_candidats_ecrit_deja_reserves(*, epreuve: Epreuve, code_uai: str) -> int:
    """
    Retourne le nombre total de candidats "papier" déjà réservés pour (epreuve, code_uai),
    toutes inscriptions confondues.

    Hypothèse : chaque inscription stocke nb_candidats_ecrit.
    """
    total = (
            InscriptionOlympiades.objects
            .filter(epreuve=epreuve, code_uai=code_uai)
            .aggregate(s=Sum("nb_candidats_ecrit"))["s"]
            or 0
    )
    return int(total)


def _generer_csv_epreuve_ecrite(*, epreuve: Epreuve, code_uai: str, nb_candidats: int) -> bytes:
    """
    Génère le CSV des identifiants pour l'épreuve écrite.

    Contrainte : identifiant = UAI + 3 chiffres.
    Donc on calcule un offset à partir du nombre déjà réservé pour ce UAI sur cette épreuve.
    """
    tampon: io.StringIO = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";")
    ecrivain.writerow(["identifiant_ecrit"])

    offset: int = _compter_candidats_ecrit_deja_reserves(epreuve=epreuve, code_uai=code_uai) - nb_candidats
    # Important :
    # - Dans le flux "inscription initiale", tu viens d'enregistrer l'inscription (nb_candidats inclus),
    #   donc le sum() inclut déjà cette inscription.
    # - On retire nb_candidats pour retrouver "le total avant cette inscription" et générer les nouveaux numéros.
    if offset < 0:
        offset = 0

    for i in range(1, nb_candidats + 1):
        numero = offset + i
        if numero > 999:
            # Contrainte dure : UAI + 3 chiffres
            raise ValueError(
                f"Trop de candidats papier pour {code_uai} sur {epreuve.nom} : dépasse 999 (actuel={numero})."
            )
        identifiant: str = f"{code_uai}{numero:03d}"
        ecrivain.writerow([identifiant])

    return tampon.getvalue().encode("utf-8")


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
        epreuve: Epreuve,
        code_uai: str,
        nb_candidats_ecrit: int,
        usernames_olympiades: List[str],
) -> List[Tuple[str, bytes]]:
    """
    Construit les pièces jointes CSV :
    - écrit : UAI + 3 chiffres, sans collision (offset BD)
    - pratique : usernames (1 par ligne)
    """
    csv_ecrit: bytes = _generer_csv_epreuve_ecrite(epreuve=epreuve, code_uai=code_uai, nb_candidats=nb_candidats_ecrit)
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


@transaction.atomic
def preparer_groupe_et_comptes_annales(
        *,
        annale: Epreuve,
        referent: User,
        email_enseignant: str,
        nb_equipes: int,
        inscription_annales: InscriptionAnnales,
) -> tuple[GroupeParticipant, List[str]]:
    """
    Crée un groupe et génère des comptes "équipes" pour une annale (plateforme uniquement).

    Version volontairement minimale :
        - 1 appel = 1 groupe
        - pas de notion de "lot"
        - pas de numéro
        - pas de table InscriptionAnnalesGroupe
        - le lien durable est : groupe inscrit à l'épreuve (via GroupeParticipeAEpreuve)

    Note :
        `inscription_annales` est volontairement présent dans la signature :
        - pour exprimer le fait qu'on rattache ces créations à une inscription logique,
        - mais on ne persiste pas de lien supplémentaire (simplicité).

    Args:
        annale: Épreuve annale cible.
        referent: Référent (propriétaire) du groupe.
        email_enseignant: Email de l'enseignant (issu du token).
        nb_equipes: Nombre de comptes "équipes" à créer (doit être > 0).
        inscription_annales: Objet logique d'inscription annales (unique pour (annale, email)).

    Returns:
        tuple[GroupeParticipant, List[str]]: (groupe créé, liste des usernames créés)

    Raises:
        ValueError: si nb_equipes <= 0.
        RuntimeError: si la création des users échoue côté `save_users`.
    """
    if nb_equipes <= 0:
        raise ValueError("nb_equipes doit être > 0")

    # Nom de groupe : simple, lisible, sans dépendance à un compteur.
    # On inclut annale.id + email pour réduire les collisions visuelles.
    # On ajoute un suffixe temporel pour éviter l'unicité de 'nom' si jamais elle existe.
    from django.utils import timezone

    horodatage: str = timezone.now().strftime("%Y%m%d-%H%M%S")
    nom_groupe: str = f"annales-{annale.id}-{email_enseignant}-{horodatage}"

    # Création du groupe : 1 génération = 1 groupe.
    groupe: GroupeParticipant = GroupeParticipant.objects.create(
        nom=nom_groupe,
        referent=referent,
    )

    # Génération des usernames (fonction existante dans ton projet).
    from login.utils import genere_participants_uniques

    usernames: List[str] = list(genere_participants_uniques(referent, nb_equipes))

    # Création des users + rattachement au groupe via ton utilitaire existant.
    resultat = save_users(groupe.id, usernames, inscription_externe_id=None)
    if resultat.get("status") != "success":
        raise RuntimeError(resultat.get("message", "Erreur lors de la création des utilisateurs"))

    # Inscription réelle du groupe à l'annale (crée UserEpreuve/UserExercice/etc.).
    annale.inscrire_groupe(groupe)

    return groupe, usernames


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