import random
import logging
import unicodedata
from datetime import timedelta
from typing import Iterable, Optional

from django.contrib.auth.models import User
from django.utils import timezone
from epreuve.models import Epreuve, Exercice, JeuDeTest, UserExercice, UserEpreuve

logger = logging.getLogger(__name__)


def assigner_participants_jeux_de_test(participants: Iterable[User], exercice: Exercice) -> None:
    """
    Attribue à chaque participant un jeu de test pour un exercice donné.

    Tous les jeux de test disponibles pour cet exercice sont mélangés aléatoirement,
    puis attribués aux participants en boucle (réutilisation possible si le nombre
    de participants dépasse le nombre de jeux de test).

    Args:
        participants (Iterable[User]): Liste des utilisateurs à qui attribuer un jeu de test.
        exercice (Exercice): L’exercice concerné.
    """
    if not exercice.avec_jeu_de_test:
        return

    # Récupère tous les jeux de test liés à cet exercice
    jeux_disponibles: list[JeuDeTest] = list(exercice.get_jeux_de_test())

    if not jeux_disponibles:
        return

    # Mélange aléatoire des jeux
    random.shuffle(jeux_disponibles)
    nb_jeux = len(jeux_disponibles)

    for i, participant in enumerate(participants):
        # Récupère ou crée l'entrée UserExercice pour ce participant
        user_exercice: UserExercice = UserExercice.objects.get(participant=participant, exercice=exercice)

        # Ne pas écraser un jeu de test déjà attribué
        if user_exercice.jeu_de_test:
            continue

        # Attribution en boucle (modulo)
        user_exercice.jeu_de_test = jeux_disponibles[i % nb_jeux]
        user_exercice.save()


def temps_restant_seconde(user_epreuve: UserEpreuve, epreuve: Epreuve) -> Optional[int]:
    """
    Calcule le temps restant en secondes pour un utilisateur participant à une épreuve,
    en tenant compte de l'heure de début de l'utilisateur et de la durée globale de l'épreuve.

    Args:
        user_epreuve (UserEpreuve): L'objet UserEpreuve représentant l'association entre l'utilisateur et l'épreuve.
        epreuve (Epreuve): L'objet Epreuve représentant l'épreuve en question.

    Returns:
        Optional[int]: Le temps restant en secondes. Retourne 0 si le temps est écoulé.
    """
    # Heure actuelle
    now = timezone.now()

    # Calcul de l'heure de fin basée sur l'heure de début de l'utilisateur et la durée de l'épreuve
    fin_epreuve_user = user_epreuve.debut_epreuve + timedelta(minutes=epreuve.duree)

    # S'assurer que le temps de fin ne dépasse pas l'heure de fin globale de l'épreuve
    fin_epreuve_user = min(fin_epreuve_user, epreuve.date_fin)

    # Calcul du temps restant
    temps_restant = fin_epreuve_user - now

    # Convertir le temps restant en secondes et s'assurer qu'il n'est pas négatif
    temps_restant_sec = max(temps_restant.total_seconds(), 0)

    return int(temps_restant_sec)


def vider_jeux_test_exercice(exercice: Exercice):
    for jeu in JeuDeTest.objects.filter(exercice=exercice):
        jeu.delete()
    exercice.separateur_reponse_jeudetest = "\n"
    exercice.separateur_jeu_test = "\n"
    exercice.save()


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text.replace('\r\n', '\n').replace('\r', '\n').strip())


def analyse_reponse_jeu_de_test(rep1: str, rep2: str) -> bool:
    lignes1 = normalize(str(rep1)).split('\n')
    lignes2 = normalize(str(rep2)).split('\n')

    if len(lignes1) != len(lignes2):
        return False

    for i, (l1, l2) in enumerate(zip(lignes1, lignes2)):
        if normalize(l1) != normalize(l2):
            return False
    return True
