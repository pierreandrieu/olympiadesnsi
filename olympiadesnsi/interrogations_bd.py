from django.contrib.auth.models import User

from epreuve.models import Epreuve
from inscription.models import GroupeParticipeAEpreuve


def user_est_inscrit_a_epreuve(user: User, epreuve: Epreuve) -> bool:
    """
    Vérifie si un utilisateur est inscrit à une épreuve.
    :param user: L'Utilisateur (django.contrib.auth.models.User)
    :param epreuve: L'épreuve (epreuve.models.Epreuve)
    :return: True si l'utilisateur est inscrit à l'épreuve, False sinon.
    """
    if not user.groups.filter(name='Participant').exists():
        return False  # Sortie anticipée si l'utilisateur n'est pas un participant

    # Récupère de manière sécurisée les appartenances de l'utilisateur aux groupes
    groupes_utilisateur = getattr(user, 'appartenances', None)
    if not groupes_utilisateur:
        return False  # L'utilisateur n'a pas d'appartenances définies

    # Récupère les IDs des groupes auxquels l'utilisateur appartient
    groupes_utilisateur_ids = groupes_utilisateur.values_list('groupe_id', flat=True)

    # Vérifie si l'un de ces groupes est inscrit à l'épreuve
    return GroupeParticipeAEpreuve.objects.filter(
        epreuve=epreuve,
        groupe_id__in=groupes_utilisateur_ids
    ).exists()
