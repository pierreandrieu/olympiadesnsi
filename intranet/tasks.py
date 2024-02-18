from typing import List, Tuple, Optional
from celery import shared_task
from django.db import transaction
from django.contrib.auth.models import User, Group

from epreuve.models import Epreuve
from inscription.utils import inscrire_groupe_a_epreuve
import logging

from inscription.models import GroupeParticipant
from intranet.models import ParticipantEstDansGroupe

logger = logging.getLogger(__name__)


@shared_task
def save_users_task(groupe_id: int, users_info: List[Tuple[str, str]],
                    epreuve_id: Optional[int]=None) -> dict:
    """
    Crée et enregistre des utilisateurs en masse, les associe à un groupe de participants
    et les inscrit à une épreuve si spécifié.

    Args:
        groupe_id (int): L'id du groupe de participants.
        users_info (List[Tuple[str, str]]): Liste des tuples contenant le nom d'utilisateur et le mot de passe.
        epreuve_id (Optional[int]): L'id de l'épreuve à laquelle le groupe sera inscrit en cas d'inscription externe.

    Returns:
        dict: Un dictionnaire indiquant le statut de l'opération.
    """
    try:
        # Début d'une transaction pour garantir l'intégrité des données
        with transaction.atomic():
            # Récupération du groupe de participants par son identifiant
            groupe = GroupeParticipant.objects.get(id=groupe_id)

            # Création des objets User sans les sauvegarder immédiatement dans la base de données
            users = [User(username=username) for username, password in users_info]
            for i, user in enumerate(users):
                user.set_password(users_info[i][1])  # Définition des mots de passe

            # Enregistrement en masse des objets User créés
            User.objects.bulk_create(users)

            # Mise à jour des instances User avec leurs ID après la création
            users = User.objects.filter(username__in=[user.username for user in users])

            # Association des utilisateurs au groupe "Participant" standard
            groupe_participant = Group.objects.get(name="Participant")
            UserGroupRelations = User.groups.through
            user_group_relations = [UserGroupRelations(user_id=user.id, group_id=groupe_participant.id) for user in
                                    users]
            UserGroupRelations.objects.bulk_create(user_group_relations)

            # Association des utilisateurs au groupe de participants personnalisé
            membres = [ParticipantEstDansGroupe(utilisateur=user, groupe=groupe) for user in users]
            ParticipantEstDansGroupe.objects.bulk_create(membres)

            # Inscription du groupe à l'épreuve si un identifiant d'épreuve est fourni
            if epreuve_id:
                epreuve = Epreuve.objects.get(id=epreuve_id)
                # Logique pour inscrire le groupe à l'épreuve et aux exercices associés
                inscrire_groupe_a_epreuve(groupe, epreuve)

    except Exception as e:
        # En cas d'erreur, mise à jour du statut du groupe et enregistrement de l'erreur
        groupe.statut = 'ECHEC'
        groupe.save()
        logger.error(f"Erreur lors de la création des utilisateurs et de leur inscription : {e}")
        return {'status': 'error', 'message': str(e)}

    # Mise à jour du statut et du nombre de membres du groupe en cas de succès
    groupe.statut = 'VALIDE'
    groupe.nb_membres = len(users_info)
    groupe.save()

    return {'status': 'success'}
