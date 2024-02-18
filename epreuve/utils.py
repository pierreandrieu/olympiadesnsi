import random
from typing import Iterable

from django.contrib.auth.models import User

from epreuve.models import Exercice, JeuDeTest, UserExercice


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
        for user_exercice in participants:
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
