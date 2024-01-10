from celery import shared_task
from django.contrib.auth.models import User, Group
from epreuve.models import UserCreePar, GroupeCreePar
from django.utils import timezone
from django.db import transaction


@shared_task
def save_users_task(nom_groupe, users_info, user_id):
    with transaction.atomic():
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

            user_creepar_associations = [UserCreePar(utilisateur=user, createur=createur, date_creation=timezone.now()) for
                                         user in users]
            UserCreePar.objects.bulk_create(user_creepar_associations)
        except Exception as e:
            # Loguez l'erreur ici
            print(f"Erreur lors de la création des utilisateurs : {e}")

        if not GroupeCreePar.objects.filter(groupe=groupe).exists():
            GroupeCreePar.objects.create(groupe=groupe,
                                         createur=createur,
                                         date_creation=timezone.now(),
                                         nombre_participants=len(users_info))
