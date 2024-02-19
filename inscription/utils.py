from typing import List

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet
from django.utils.crypto import get_random_string

from epreuve.models import Exercice, Epreuve, UserEpreuve, UserExercice
from inscription.models import GroupeParticipeAEpreuve, GroupeParticipant, InscriptionExterne
from olympiadesnsi.constants import TOKEN_LENGTH


def inscrire_groupe_a_epreuve(groupe: GroupeParticipant, epreuve: Epreuve) -> None:
    """
    Inscription d'un groupe de participants à une épreuve, incluant l'inscription à tous les exercices de l'épreuve.

    Args:
        groupe (GroupeParticipant): Le groupe de participants à inscrire.
        epreuve (Epreuve): L'épreuve à laquelle le groupe est inscrit.

    Cette fonction crée une instance de GroupeParticipeAEpreuve pour lier le groupe à l'épreuve,
    puis inscrit chaque membre du groupe à l'épreuve et à tous ses exercices en utilisant `bulk_create`
    pour optimiser les performances de la base de données.
    """
    # Récupération des membres du groupe
    membres: QuerySet[User] = User.objects.filter(appartenances__groupe=groupe)

    # Récupération des exercices de l'épreuve
    exercices: List[Exercice] = list(Exercice.objects.filter(epreuve=epreuve))
    user_epreuves_to_create: List[UserEpreuve] = []
    user_exercices_to_create: List[UserExercice] = []

    with transaction.atomic():
        # Création de l'inscription du groupe à l'épreuve
        GroupeParticipeAEpreuve.objects.create(groupe=groupe, epreuve=epreuve)
        # Préparation des objets UserEpreuve et UserExercice pour chaque membre
        for participant in membres:
            user_epreuves_to_create.append(UserEpreuve(participant=participant, epreuve=epreuve))
            for exercice in exercices:
                user_exercices_to_create.append(UserExercice(exercice=exercice, participant=participant))

        # Insertion en masse des objets UserEpreuve et UserExercice
        UserEpreuve.objects.bulk_create(user_epreuves_to_create)
        UserExercice.objects.bulk_create(user_exercices_to_create)


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
