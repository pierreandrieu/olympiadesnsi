import logging
from datetime import datetime
from typing import List, Optional

from django.contrib.auth.models import User, Group
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import QuerySet
from django.utils.crypto import get_random_string

from epreuve.models import Epreuve

from inscription.models import GroupeParticipant, InscriptionExterne, InscripteurExterne
from intranet.models import ParticipantEstDansGroupe
from olympiadesnsi import settings
from olympiadesnsi.constants import TOKEN_LENGTH


logger = logging.getLogger(__name__)


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


def calculer_nombre_inscrits(epreuve: Epreuve, inscripteur_externe: InscripteurExterne) -> int:
    """
    Calcule le nombre total d'utilisateurs inscrits dans des groupes participants
    qui sont inscrits à une épreuve donnée et liés à un inscripteur externe spécifique.

    Args:
        epreuve (Epreuve): L'instance de l'épreuve concernée.
        inscripteur_externe (InscripteurExterne): L'instance de l'inscripteur externe concerné.

    Returns:
        int: Le nombre total d'utilisateurs inscrits dans les groupes correspondants.
    """

    # Récupérer tous les groupes liés à l'épreuve et à l'inscripteur externe spécifique
    groupes: QuerySet[GroupeParticipant] = GroupeParticipant.objects.filter(
        inscription_externe__epreuve=epreuve,
        inscription_externe__inscripteur=inscripteur_externe
    )

    # Initialiser le compteur du nombre total de participants
    total_participants: int = 0

    # Pour chaque groupe, ajouter le nombre de ses participants au total
    for groupe in groupes:
        total_participants += groupe.get_nombre_participants()

    return total_participants


def save_users(groupe_id: int, usernames: List[str],
               inscription_externe_id: Optional[int] = None) -> dict:
    """
    Crée et enregistre des utilisateurs en masse (sans mot de passe) associe à un groupe de participants
    et les inscrit à une épreuve si spécifié.

    Args:
        groupe_id (int): L'id du groupe de participants.
        usernames (List[str]): Liste des noms d'utilisateurs à ajouter.
        inscription_externe_id (Optional[int]): L'id de l'inscription externe si les participants sont créés par
        un inscripteur externe.

    Returns:
        dict: Un dictionnaire indiquant le statut de l'opération.
    """
    try:
        groupe: GroupeParticipant = GroupeParticipant.objects.get(id=groupe_id)
    except GroupeParticipant.DoesNotExist:
        return {'status': 'error', 'message': f"Groupe {groupe_id} introuvable"}
    try:
        # Début d'une transaction pour garantir l'intégrité des données
        with transaction.atomic():
            # Récupération du groupe de participants par son identifiant
            groupe.statut = "CREATION"

            groupe.save()

            # Création des objets User sans les sauvegarder immédiatement dans la base de données
            users: List[User] = [User(username=username) for username in usernames]

            # Enregistrement en masse des objets User créés
            User.objects.bulk_create(users)

            # Mise à jour des instances User avec leurs ID après la création
            users: QuerySet[User] = User.objects.filter(username__in=[user.username for user in users])

            # Association des utilisateurs au groupe "Participant" standard
            groupe_participant: Group = Group.objects.get(name="Participant")
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
                inscription_externe.epreuve.inscrire_participants(users)
                email = inscription_externe.inscripteur.email
                epreuve_nom = inscription_externe.epreuve.nom
                nb_equipes = len(usernames)
                intro_phrase = (
                    "Veuillez trouver ci-joint les identifiants de l’équipe que vous avez inscrite."
                    if nb_equipes == 1
                    else f"Veuillez trouver ci-joint les identifiants des {nb_equipes} équipes que vous avez inscrites."
                )

                body = (
                    "Bonjour,\n\n"
                    f"{intro_phrase} Chaque équipe devra choisir un mot de passe lors de sa première connexion.\n\n"
                    "En cas d’oubli du mot de passe, il est possible depuis la page d’accueil de réinitialiser le mot de passe d'un compte à partir de l'email utilisé pour l'inscription.\n\n"
                    "Pour rappel, l’épreuve pratique des Olympiades de NSI se déroule sur trois jours. Chaque enseignant choisit librement "
                    "le créneau qui lui convient pour faire participer ses élèves. Afin d’éviter tout accès anticipé à l’épreuve, "
                    "nous vous demandons de ne transmettre les identifiants aux élèves qu’au moment retenu. "
                    "L’épreuve d’entraînement reste quant à elle accessible sans restriction.\n\n"
                    "Nous espérons que vos élèves prendront plaisir à participer à cette épreuve, et vous remercions pour l’intérêt que vous portez "
                    "aux Olympiades de NSI. Bonnes olympiades ! \n\n"
                    "Bien cordialement,\n"
                    "L’équipe des Olympiades de NSI"
                )

                mail = EmailMessage(
                    subject=f"Inscription à {inscription_externe.epreuve.nom}",
                    body=body,
                    from_email=f"{settings.ADMIN_NAME} <{settings.EMAIL_HOST_USER}>",
                    to=[email],
                )

                # Ajout de la pièce jointe
                mail.attach(
                    filename=f"identifiants_equipes_{epreuve_nom}_{datetime.now().strftime('%d-%m_%H-%M')}.csv",
                    content="username\n" +
                            "\n".join([f"{user}" for user in usernames]),
                    mimetype='text/csv')

                # Envoi de l'email
                mail.send()

            groupe.statut = 'VALIDE'
            groupe.save()
            return {'status': 'success', 'email': email, 'epreuve_nom': epreuve_nom, 'usernames': usernames}

    except Exception as e:
        # En cas d'erreur, mise à jour du statut du groupe et enregistrement de l'erreur
        groupe.statut = 'ECHEC'
        groupe.save()
        return {'status': 'error', 'message': str(e)}
