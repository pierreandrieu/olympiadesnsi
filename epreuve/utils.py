import logging
import unicodedata


logger = logging.getLogger(__name__)


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text.replace('\r\n', '\n').replace('\r', '\n').strip())


def est_valide_reponse_jeu_de_test(rep1: str, rep2: str) -> bool:
    """
    Compare deux chaînes représentant des réponses à un jeu de test ligne par ligne,
    après normalisation (espaces, accents, etc.).

    Args:
        rep1 (str): Réponse attendue (ex : depuis la base de données).
        rep2 (str): Réponse soumise (ex : depuis le code de l’élève).

    Returns:
        bool: True si les deux réponses sont équivalentes ligne par ligne, False sinon.
    """
    # Normalisation et découpage en lignes
    lignes1 = normalize(str(rep1)).split('\n')
    lignes2 = normalize(str(rep2)).split('\n')

    # Si le nombre de lignes diffère, on considère que les réponses ne sont pas valides
    if len(lignes1) != len(lignes2):
        return False

    # Comparaison ligne par ligne après normalisation
    for i, (l1, l2) in enumerate(zip(lignes1, lignes2)):
        if normalize(l1) != normalize(l2):
            return False

    # Si toutes les lignes sont égales, on considère la réponse comme valide
    return True


def get_cache_key_liste_epreuves_publiques() -> str:
    """
    Renvoie la clé de cache utilisée pour la liste des épreuves publiques.
    """
    return "cache_liste_epreuves_publiques"
