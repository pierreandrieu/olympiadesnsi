from __future__ import annotations

from typing import Iterable, List, Optional, Set, Type

from django.apps import apps
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


def _cle_cache_nb_participants(epreuve_id: int) -> str:
    """
    Clé de cache utilisée par `Epreuve.compte_participants_inscrits()`.
    """
    return f"epreuve_{epreuve_id}_nombre_participants"


def _modele_groupe_participe_a_epreuve() -> Type[models.Model]:
    """
    Récupère dynamiquement le modèle through `inscription.GroupeParticipeAEpreuve`.
    Évite les imports directs et les dépendances circulaires.
    """
    return apps.get_model("inscription", "GroupeParticipeAEpreuve")


def _modele_participant_est_dans_groupe() -> Type[models.Model]:
    """
    Récupère dynamiquement le modèle d’appartenance `intranet.ParticipantEstDansGroupe`.
    Évite les imports directs et les dépendances circulaires.
    """
    return apps.get_model("intranet", "ParticipantEstDansGroupe")


def _epreuve_ids_pour_groupe(groupe_id: int) -> List[int]:
    """
    Retourne la liste des IDs d'épreuves auxquelles le groupe est inscrit.
    """
    modele_through = _modele_groupe_participe_a_epreuve()

    # NB: on suppose que le through a bien des champs `epreuve_id` et `groupe_id`
    ids: List[int] = list(
        modele_through.objects.filter(groupe_id=groupe_id).values_list("epreuve_id", flat=True)
    )
    return ids


def _invalider_cache_epreuves(epreuve_ids: Iterable[int]) -> None:
    """
    Invalide en une seule fois les caches des épreuves fournies.
    """
    ids_uniques: Set[int] = set(epreuve_ids)
    if not ids_uniques:
        return

    cles: List[str] = [_cle_cache_nb_participants(epreuve_id) for epreuve_id in ids_uniques]
    cache.delete_many(cles)


# ------------------------------------------------------------
# 1) Invalidation quand on modifie le lien Epreuve <-> Groupe
# ------------------------------------------------------------

@receiver(post_save, sender=_modele_groupe_participe_a_epreuve())
def invalider_cache_apres_inscription_groupe_a_epreuve(
        sender,
        instance: models.Model,
        created: bool,
        **kwargs,
) -> None:
    """
    Invalide le cache du nombre de participants lorsqu'un groupe est inscrit (ou modifié)
    sur une épreuve via `GroupeParticipeAEpreuve`.
    """
    # `instance` est un GroupeParticipeAEpreuve-like, donc possède `epreuve_id`
    epreuve_id: Optional[int] = getattr(instance, "epreuve_id", None)
    if epreuve_id is None:
        return
    cache.delete(_cle_cache_nb_participants(epreuve_id))


@receiver(post_delete, sender=_modele_groupe_participe_a_epreuve())
def invalider_cache_apres_desinscription_groupe_a_epreuve(
        sender,
        instance: models.Model,
        **kwargs,
) -> None:
    """
    Invalide le cache du nombre de participants lorsqu'un groupe est désinscrit
    d'une épreuve via suppression de `GroupeParticipeAEpreuve`.
    """
    epreuve_id: Optional[int] = getattr(instance, "epreuve_id", None)
    if epreuve_id is None:
        return
    cache.delete(_cle_cache_nb_participants(epreuve_id))


# ------------------------------------------------------------
# 2) Invalidation quand la taille d’un groupe change
# ------------------------------------------------------------

@receiver(post_save, sender=_modele_participant_est_dans_groupe())
def invalider_cache_apres_ajout_membre_dans_groupe(
        sender,
        instance: models.Model,
        created: bool,
        **kwargs,
) -> None:
    """
    Invalide le cache des épreuves liées à un groupe lorsqu’un membre est ajouté au groupe.

    Même si `created=False` (modif), on invalide quand même : c'est peu coûteux
    et évite les cas bizarres.
    """
    groupe_id: Optional[int] = getattr(instance, "groupe_id", None)
    if groupe_id is None:
        return

    epreuve_ids: List[int] = _epreuve_ids_pour_groupe(groupe_id)
    _invalider_cache_epreuves(epreuve_ids)


@receiver(post_delete, sender=_modele_participant_est_dans_groupe())
def invalider_cache_apres_retrait_membre_dans_groupe(
        sender,
        instance: models.Model,
        **kwargs,
) -> None:
    """
    Invalide le cache des épreuves liées à un groupe lorsqu’un membre est retiré du groupe.
    """
    groupe_id: Optional[int] = getattr(instance, "groupe_id", None)
    if groupe_id is None:
        return

    epreuve_ids: List[int] = _epreuve_ids_pour_groupe(groupe_id)
    _invalider_cache_epreuves(epreuve_ids)
