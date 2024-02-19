from typing import List, Tuple

from django.contrib.auth.models import User
from django.utils.crypto import get_random_string

from inscription.models import CompteurParticipantsAssocies
import olympiadesnsi.constants as constantes


def genere_mot_de_passe(taille: int = constantes.TAILLE_MDP) -> str:
    """
    Génère un mot de passe aléatoire.

    Args:
        taille (int): La longueur du mot de passe à générer.

    Returns:
        str: Le mot de passe généré.
    """
    return get_random_string(length=taille, allowed_chars='abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789')


def genere_participants_uniques(referent: User, nb: int, taille_mdp: int = constantes.TAILLE_MDP) \
        -> List[Tuple[str, str]]:
    """
    Génère une liste de tuples contenant des noms d'utilisateurs uniques et des mots de passe pour un référent donné.

    Args:
        referent (User): L'utilisateur référent pour lequel générer les participants.
        nb (int): Le nombre de participants à générer.
        taille_mdp (int, optional): La longueur des mots de passe à générer. Par défaut à 12.

    Returns:
        List[Tuple[str, str]]: Liste de tuples, chaque tuple contenant un nom d'utilisateur unique et un mot de passe.
    """
    # Génération d'une partie aléatoire et du faux ID basé sur l'ID du référent
    faux_id = str(2 * referent.id + 100)

    # Récupération du nombre de participants déjà administrés par le référent
    compteur, _ = CompteurParticipantsAssocies.objects.get_or_create(organisateur=referent)
    nb_participants_administres = compteur.nb_participants_associes

    # Génération des noms d'utilisateurs et mots de passe
    utilisateurs_mdp = [
        (
            f"{get_random_string(length=4, allowed_chars='abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ')}"
            f"{faux_id}"
            f"{(nb_participants_administres + i + 1):03d}",
            genere_mot_de_passe(taille_mdp)) for i in range(nb)
    ]

    # Mise à jour du compteur de participants associés
    compteur.nb_participants_associes += nb
    compteur.save()

    return utilisateurs_mdp
