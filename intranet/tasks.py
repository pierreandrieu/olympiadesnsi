from datetime import datetime
from typing import List, Tuple, Optional
from celery import shared_task
from django.core.mail import EmailMessage
from django.db import transaction
from django.contrib.auth.models import User, Group
from django.db.models import QuerySet

from inscription.utils import inscrire_groupe_a_epreuve
import logging

from inscription.models import GroupeParticipant, InscriptionExterne
from intranet.models import ParticipantEstDansGroupe
from olympiadesnsi import settings

logger = logging.getLogger(__name__)


@shared_task
def save_users_task(groupe_id: int, users_info: List[Tuple[str, str]],
                    inscription_externe_id: Optional[int] = None) -> dict:
    """
    Crée et enregistre des utilisateurs en masse, les associe à un groupe de participants
    et les inscrit à une épreuve si spécifié.

    Args:
        groupe_id (int): L'id du groupe de participants.
        users_info (List[Tuple[str, str]]): Liste des tuples contenant le nom d'utilisateur et le mot de passe.
        inscription_externe_id (Optional[int]): L'id de l'inscription externe si les participants sont créés par
        un inscripteur externe.

    Returns:
        dict: Un dictionnaire indiquant le statut de l'opération.
    """
    try:
        # Début d'une transaction pour garantir l'intégrité des données
        with transaction.atomic():
            logger.debug("debut")

            # Récupération du groupe de participants par son identifiant
            groupe: GroupeParticipant = GroupeParticipant.objects.get(id=groupe_id)
            logger.debug(f"{groupe.statut}")

            groupe.statut = "CREATION"

            groupe.save()
            logger.debug(f"{groupe.statut}")

            logger.debug(f"groupe statut modifie {groupe.statut}")

            # Création des objets User sans les sauvegarder immédiatement dans la base de données
            users: List[User] = [User(username=username) for username, password in users_info]
            for i, user in enumerate(users):
                user.set_password(users_info[i][1])  # Définition des mots de passe
                logger.debug(f"{users_info[i][0]}{users_info[i][1]}")

            # Enregistrement en masse des objets User créés
            User.objects.bulk_create(users)

            # Mise à jour des instances User avec leurs ID après la création
            users: QuerySet[User] = User.objects.filter(username__in=[user.username for user in users])

            # Association des utilisateurs au groupe "Participant" standard
            groupe_participant: Group = Group.objects.get(name="Participant")
            logger.debug(f"dans {groupe.nom}")
            UserGroupRelations = User.groups.through
            user_group_relations = [UserGroupRelations(user_id=user.id, group_id=groupe_participant.id) for user in
                                    users]
            UserGroupRelations.objects.bulk_create(user_group_relations)

            # Association des utilisateurs au groupe de participants personnalisé
            membres: List[ParticipantEstDansGroupe] = [ParticipantEstDansGroupe(utilisateur=user, groupe=groupe)
                                                       for user in users]
            ParticipantEstDansGroupe.objects.bulk_create(membres)

            email: Optional[str] = None
            epreuve_nom: Optional[str] = None
            # Inscription du groupe à l'épreuve si un identifiant d'épreuve est fourni
            if inscription_externe_id:
                inscription_externe: InscriptionExterne = InscriptionExterne.objects.get(id=inscription_externe_id)
                # Logique pour inscrire le groupe à l'épreuve et aux exercices associés
                inscrire_groupe_a_epreuve(groupe=groupe, epreuve=inscription_externe.epreuve, participants=users)
                email = inscription_externe.inscripteur.email
                epreuve_nom = inscription_externe.epreuve.nom
                mail = EmailMessage(
                    subject=f"Inscription à {inscription_externe.epreuve.nom}",
                    body=f"Veuillez trouver ci-joint les identifiants et mots de passe "
                         f"des {len(users_info)} participants. "
                         f"Les mots de passe peuvent être modifiés dans l'intranet.",
                    from_email=settings.EMAIL_HOST_USER,
                    to=[email],
                )

                # Ajout de la pièce jointe
                mail.attach(filename=f"identifiants_participants_{epreuve_nom}_{datetime.now().strftime('%d-%m_%H-%M')}",
                            content="Nom d'utilisateur,mot de passe\n" +
                                    "\n".join([f"{user},{pwd}" for user, pwd in users_info]),
                            mimetype='text/csv')

                # Envoi de l'email
                mail.send()

            groupe.statut = 'VALIDE'
            logger.debug(f"{groupe.statut}")
            groupe.save()
            return {'status': 'success', 'email': email, 'epreuve_nom': epreuve_nom, 'users_info': users_info}

    except Exception as e:
        # En cas d'erreur, mise à jour du statut du groupe et enregistrement de l'erreur
        groupe.statut = 'ECHEC'
        groupe.save()
        logger.debug(f"Erreur lors de la création des utilisateurs et de leur inscription : {e}")
        logger.error(f"Erreur lors de la création des utilisateurs et de leur inscription : {e}")
        return {'status': 'error', 'message': str(e)}
