import logging
from datetime import datetime
from typing import List, Iterable, Optional

from django.contrib.auth.models import User, Group
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import QuerySet
from django.utils.crypto import get_random_string

from epreuve.models import Exercice, Epreuve, UserEpreuve, UserExercice
from epreuve.utils import assigner_participants_jeux_de_test

from inscription.models import GroupeParticipeAEpreuve, GroupeParticipant, InscriptionExterne, InscripteurExterne
from intranet.models import ParticipantEstDansGroupe
from olympiadesnsi import settings
from olympiadesnsi.constants import TOKEN_LENGTH


logger = logging.getLogger(__name__)


def inscrire_participants_a_epreuve(participants: Iterable[User], epreuve: Epreuve) -> None:
    """
    Inscription de participants à une épreuve, incluant l'inscription à tous les exercices de l'épreuve.

    Args:
        participants (QuerySet[User]): Les nouveaux utilisateurs du groupe
        epreuve (Epreuve): L'épreuve à laquelle le groupe est inscrit.

    Inscrit chaque participant à l'épreuve et à tous ses exercices en utilisant `bulk_create`
    pour optimiser les performances de la base de données.
    """
    # Récupération des membres du groupe

    # Récupération des exercices de l'épreuve
    exercices: List[Exercice] = list(Exercice.objects.filter(epreuve=epreuve))
    user_epreuves_to_create: List[UserEpreuve] = []
    user_exercices_to_create: List[UserExercice] = []

    with transaction.atomic():
        # Préparation des objets UserEpreuve et UserExercice pour chaque membre
        for participant in participants:
            user_epreuves_to_create.append(UserEpreuve(participant=participant, epreuve=epreuve))
            for exercice in exercices:
                user_exercices_to_create.append(UserExercice(exercice=exercice, participant=participant))

        # Insertion en masse des objets UserEpreuve et UserExercice
        UserEpreuve.objects.bulk_create(user_epreuves_to_create)
        UserExercice.objects.bulk_create(user_exercices_to_create)

        for exercice in exercices:
            if exercice.avec_jeu_de_test:
                assigner_participants_jeux_de_test(participants, exercice)


def inscrire_groupe_a_epreuve(groupe: GroupeParticipant, epreuve: Epreuve,
                              participants: Optional[Iterable[User]] = None) -> None:
    """
    Inscription d'un groupe de participants à une épreuve, incluant l'inscription à tous les exercices de l'épreuve.

    Args:
        groupe (GroupeParticipant): Le groupe de participants à inscrire.
        epreuve (Epreuve): L'épreuve à laquelle le groupe est inscrit.
        participants (Iterable[User]): les participants à inscrire si on ne veut pas inscrire tous les membres du groupe
        Par exemple dans le cas où le groupe est complété par de nouveaux participants

    Cette fonction crée une instance de GroupeParticipeAEpreuve pour lier le groupe à l'épreuve,
    puis inscrit chaque membre du groupe à l'épreuve et à tous ses exercices en utilisant `bulk_create`
    pour optimiser les performances de la base de données.
    """
    with transaction.atomic():
        # Création de l'inscription du groupe à l'épreuve
        GroupeParticipeAEpreuve.objects.get_or_create(groupe=groupe, epreuve=epreuve)
        if not participants:
            participants: Iterable[User] = groupe.participants()
        inscrire_participants_a_epreuve(participants, epreuve)


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
                inscrire_groupe_a_epreuve(groupe=groupe, epreuve=inscription_externe.epreuve, participants=users)
                email = inscription_externe.inscripteur.email
                epreuve_nom = inscription_externe.epreuve.nom
                mail = EmailMessage(
                    subject=f"Inscription à {inscription_externe.epreuve.nom}",
                    body=f"Veuillez trouver ci-joint les identifiants "
                         f"des {len(usernames)} équipes. "
                         f"Les mots de passe devront être définis à la première connexion.\n"
                         f"En cas de perte de mot de passe par une équipe, vous pourrez utiliser l'onglet de "
                         f"récupération de compte sur la page principale des olympiades.",
                    from_email=settings.EMAIL_HOST_USER,
                    to=[email],
                )

                # Ajout de la pièce jointe
                mail.attach(
                    filename=f"identifiants_participants_{epreuve_nom}_{datetime.now().strftime('%d-%m_%H-%M')}",
                    content="Nom d'utilisateur\n" +
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
