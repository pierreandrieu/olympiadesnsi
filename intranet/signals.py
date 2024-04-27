# signals.py

from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.core.cache import cache
from .models import ParticipantEstDansGroupe


@receiver(m2m_changed, sender=ParticipantEstDansGroupe)
def update_participant_count(sender, instance: ParticipantEstDansGroupe, action: str, **kwargs):
    """
    Signal pour mettre à jour le cache du nombre de participants lorsque des membres sont ajoutés ou supprimés
    d'un groupe.

    Args:
        sender (Model class): La classe du modèle qui envoie le signal.
        instance (ParticipantEstDansGroupe): L'instance de la relation qui a été modifiée.
        action (str): Le type d'action qui a déclenché le signal (ajout, suppression, etc.).
    """
    # On ne réagit qu'aux actions post ajout, suppression ou vidage complet de la liste
    if action in ["post_add", "post_remove", "post_clear"]:
        groupe = instance.groupe if hasattr(instance, 'groupe') else instance
        cache_key = f'nombre_participants_{groupe.id}'
        cache.delete(cache_key)
