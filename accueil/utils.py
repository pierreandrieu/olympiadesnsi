from django.core.cache import cache
from typing import List, Dict

from epreuve.models import Epreuve


def get_epreuves_publiques_info() -> List[Dict[str, object]]:
    """
    Retourne les informations affichables des épreuves publiques
    (nom et nombre de participants), avec mise en cache pendant 24 heures.

    Returns:
        List[dict]: Liste de dictionnaires {nom, nombre_participants}
    """
    cache_key = "liste_epreuves_publiques_info"
    donnees = cache.get(cache_key)

    if donnees is None:
        donnees = [
            {
                "nom": e.nom,
                "nombre_participants": e.compte_participants_inscrits()
            }
            for e in Epreuve.liste_epreuves_publiques()
        ]
        cache.set(cache_key, donnees, timeout=86400)  # 24 heures

    return donnees
