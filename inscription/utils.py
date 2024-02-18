from typing import List

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet

from epreuve.models import Exercice, Epreuve, UserEpreuve, UserExercice
from inscription.models import GroupeParticipeAEpreuve, GroupeParticipant


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
    print("ok")
    membres: QuerySet[User] = User.objects.filter(appartenances__groupe=groupe)
    print("membres = ", membres)

    # Récupération des exercices de l'épreuve
    exercices: List[Exercice] = list(Exercice.objects.filter(epreuve=epreuve))
    print("exercices = ", exercices)
    user_epreuves_to_create: List[UserEpreuve] = []
    user_exercices_to_create: List[UserExercice] = []

    with transaction.atomic():
        # Création de l'inscription du groupe à l'épreuve
        GroupeParticipeAEpreuve.objects.create(groupe=groupe, epreuve=epreuve)
        print("1")
        # Préparation des objets UserEpreuve et UserExercice pour chaque membre
        for participant in membres:
            user_epreuves_to_create.append(UserEpreuve(participant=participant, epreuve=epreuve))
            for exercice in exercices:
                user_exercices_to_create.append(UserExercice(exercice=exercice, participant=participant))
        print(user_epreuves_to_create)
        print(user_exercices_to_create)
        # Insertion en masse des objets UserEpreuve et UserExercice
        UserEpreuve.objects.bulk_create(user_epreuves_to_create)
        UserExercice.objects.bulk_create(user_exercices_to_create)
