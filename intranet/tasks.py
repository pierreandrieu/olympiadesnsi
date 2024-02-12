from celery import shared_task
from django.contrib.auth.models import User, Group
from intranet.models import GroupeCreePar
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


@shared_task
def save_users_task(nom_groupe, users_info, user_id):
    try:
        with transaction.atomic():
            groupe_participants, created = Group.objects.get_or_create(name="Participant")
            createur = User.objects.get(id=user_id)

            users = []
            for username, password in users_info:
                user = User(username=username)
                user.set_password(password)
                users.append(user)

            try:
                groupe = Group.objects.create(name=nom_groupe)
                User.objects.bulk_create(users)
                groupe.user_set.add(*users)
                groupe_participants.user_set.add(*users)

            except Exception as e:
                logger.error(f"Erreur lors de la création des utilisateurs : {e}")

            if not GroupeCreePar.objects.filter(groupe=groupe).exists():
                GroupeCreePar.objects.create(groupe=groupe,
                                             createur=createur,
                                             date_creation=timezone.now(),
                                             nombre_participants=len(users_info))
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des utilisateurs : {e}")
        return {'status': 'error', 'message': str(e)}
    return {'status': 'success'}
