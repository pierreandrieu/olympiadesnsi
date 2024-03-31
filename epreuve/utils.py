import random
import logging
from datetime import timedelta
from typing import Iterable, Optional
from django.contrib.auth.models import User
from django.utils import timezone
from epreuve.models import Epreuve, Exercice, JeuDeTest, UserExercice, UserEpreuve

logger = logging.getLogger(__name__)


def assigner_participants_jeux_de_test(participants: Iterable[User], exercice: Exercice):
    if exercice.avec_jeu_de_test:
        # Récupérer tous les ID des Jeux de Test pour cet exercice
        jeux_de_test_ids = set(JeuDeTest.objects.filter(exercice=exercice).values_list('id', flat=True))
        # Récupérer les ID des Jeux de Test déjà attribués
        jeux_attribues_ids = set(UserExercice.objects.filter(exercice=exercice, jeu_de_test__isnull=False)
                                 .values_list('jeu_de_test_id', flat=True))
        # Calculer les jeux de tests non attribués
        jeux_non_attribues = jeux_de_test_ids - jeux_attribues_ids

        jeux_non_attribues_copie = list(jeux_non_attribues)
        random.shuffle(jeux_non_attribues_copie)
        # Trouver les participants sans jeu de test attribué

        cpt = 0
        fusion: bool = True
        # Pour chaque participant
        for participant in participants:
            # on récupère l'association User / Exercice
            user_exercice: UserExercice = UserExercice.objects.get(participant=participant, exercice=exercice)
            logger.debug("user = " + str(user_exercice.participant.username) + " exercice = " + str(user_exercice.exercice.titre))
            if cpt == len(jeux_non_attribues_copie):
                cpt = 0
                if fusion:
                    for id_jeu_attribue in jeux_attribues_ids:
                        jeux_non_attribues_copie.append(id_jeu_attribue)
                        fusion = False
                random.shuffle(jeux_non_attribues_copie)

            jeu_de_test_id = jeux_non_attribues_copie[cpt]
            cpt += 1

            user_exercice.jeu_de_test_id = jeu_de_test_id
            user_exercice.save()


def redistribuer_jeux_de_test_exercice(exercice: Exercice):
    # Récupérer tous les ID des Jeux de Test pour cet exercice
    jeux_de_test_ids = JeuDeTest.objects.filter(exercice=exercice).values_list('id', flat=True)
    jeux_de_test_list = list(jeux_de_test_ids)
    random.shuffle(jeux_de_test_list)
    # Trouver les participants sans jeu de test attribué
    participants = UserExercice.objects.filter(exercice=exercice)
    cpt = 0
    for user_exercice in participants:
        if cpt == len(jeux_de_test_list):
            cpt = 0
            random.shuffle(jeux_de_test_list)

        jeu_de_test_id = jeux_de_test_list[cpt]
        cpt += 1

        user_exercice.jeu_de_test_id = jeu_de_test_id
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
