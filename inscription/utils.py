import logging
from typing import List, Iterable, Optional

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet
from django.utils.crypto import get_random_string

from epreuve.models import Exercice, Epreuve, UserEpreuve, UserExercice
from epreuve.utils import assigner_participants_jeux_de_test

from inscription.models import GroupeParticipeAEpreuve, GroupeParticipant, InscriptionExterne, InscripteurExterne
from olympiadesnsi.constants import TOKEN_LENGTH


logger = logging.getLogger(__name__)


def inscrire_participants_a_epreuve(participants: Iterable[User], epreuve: Epreuve) -> None:
    """
    Inscription de participants à une épreuve, incluant l'inscription à tous les exercices de l'épreuve.

    Args:
        participants (QuerySet[User]): Les nouveaux utilisateurs du groupe
        epreuve (Epreuve): L'épreuve à laquelle le groupe est inscrit.

    Inscrit chaque participant à l'épreuve et à tous ses exercices en utilisant `bulk_create`
    pour optimiser les performances de la base de données.
    """
    # Récupération des membres du groupe

    # Récupération des exercices de l'épreuve
    exercices: List[Exercice] = list(Exercice.objects.filter(epreuve=epreuve))
    user_epreuves_to_create: List[UserEpreuve] = []
    user_exercices_to_create: List[UserExercice] = []

    with transaction.atomic():
        # Préparation des objets UserEpreuve et UserExercice pour chaque membre
        for participant in participants:
            user_epreuves_to_create.append(UserEpreuve(participant=participant, epreuve=epreuve))
            for exercice in exercices:
                user_exercices_to_create.append(UserExercice(exercice=exercice, participant=participant))

        # Insertion en masse des objets UserEpreuve et UserExercice
        UserEpreuve.objects.bulk_create(user_epreuves_to_create)
        UserExercice.objects.bulk_create(user_exercices_to_create)

        for exercice in exercices:
            if exercice.avec_jeu_de_test:
                assigner_participants_jeux_de_test(participants, exercice)


def inscrire_groupe_a_epreuve(groupe: GroupeParticipant, epreuve: Epreuve,
                              participants: Optional[Iterable[User]] = None) -> None:
    """
    Inscription d'un groupe de participants à une épreuve, incluant l'inscription à tous les exercices de l'épreuve.

    Args:
        groupe (GroupeParticipant): Le groupe de participants à inscrire.
        epreuve (Epreuve): L'épreuve à laquelle le groupe est inscrit.
        participants (Iterable[User]): les participants à inscrire si on ne veut pas inscrire tous les membres du groupe
        Par exemple dans le cas où le groupe est complété par de nouveaux participants

    Cette fonction crée une instance de GroupeParticipeAEpreuve pour lier le groupe à l'épreuve,
    puis inscrit chaque membre du groupe à l'épreuve et à tous ses exercices en utilisant `bulk_create`
    pour optimiser les performances de la base de données.
    """
    with transaction.atomic():
        # Création de l'inscription du groupe à l'épreuve
        GroupeParticipeAEpreuve.objects.get_or_create(groupe=groupe, epreuve=epreuve)
        if not participants:
            participants: Iterable[User] = groupe.participants()
        inscrire_participants_a_epreuve(participants, epreuve)


def generate_unique_token(taille: int = TOKEN_LENGTH) -> str:
    """
    Génère un token unique de longueur 50 qui n'existe pas déjà dans la base de données.

    Returns:
    - str: Un token unique.
    """
    # Initialisation d'une variable pour le token
    token: str = get_random_string(length=taille)
    # Vérifie si le token existe déjà dans la base de données
    while InscriptionExterne.objects.filter(token=token).exists():
        # Génère un nouveau token tant qu'un token identique est trouvé
        token = get_random_string(length=taille)
    return token


def calculer_nombre_inscrits(epreuve: Epreuve, inscripteur_externe: InscripteurExterne) -> int:
    """
    Calcule le nombre total d'utilisateurs inscrits dans des groupes participants
    qui sont inscrits à une épreuve donnée et liés à un inscripteur externe spécifique.

    Args:
        epreuve (Epreuve): L'instance de l'épreuve concernée.
        inscripteur_externe (InscripteurExterne): L'instance de l'inscripteur externe concerné.

    Returns:
        int: Le nombre total d'utilisateurs inscrits dans les groupes correspondants.
    """

    # Récupérer tous les groupes liés à l'épreuve et à l'inscripteur externe spécifique
    groupes: QuerySet[GroupeParticipant] = GroupeParticipant.objects.filter(
        inscription_externe__epreuve=epreuve,
        inscription_externe__inscripteur=inscripteur_externe
    )

    # Initialiser le compteur du nombre total de participants
    total_participants: int = 0

    # Pour chaque groupe, ajouter le nombre de ses participants au total
    for groupe in groupes:
        total_participants += groupe.get_nombre_participants()

    return total_participants
