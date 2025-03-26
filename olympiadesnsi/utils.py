from hashids import Hashids
from typing import Optional, Type, TypeVar
from django.db.models import Model
from olympiadesnsi.constants import HASHID_SALT, HASHID_MIN_LENGTH

# Type générique pour les modèles Django
M = TypeVar("M", bound=Model)

# Instance globale de Hashids
hashids = Hashids(salt=HASHID_SALT, min_length=HASHID_MIN_LENGTH)


def encode_id(id_: int) -> str:
    """
    Encode un identifiant entier en une chaîne hashée.

    Args:
        id_ (int): L'identifiant numérique à encoder.

    Returns:
        str: La chaîne hashée correspondante.
    """
    return hashids.encode(id_)


def decode_id(hashid: str) -> Optional[int]:
    """
    Décode une chaîne hashée en identifiant numérique.

    Args:
        hashid (str): La chaîne hashée à décoder.

    Returns:
        Optional[int]: L'identifiant original, ou None si la chaîne est invalide.
    """
    ids = hashids.decode(hashid)
    return ids[0] if ids else None


def get_object_from_hashid(model_class: Type[M], hashid: str) -> Optional[M]:
    """
    Récupère un objet Django à partir d'un identifiant encodé.

    Args:
        model_class (Type[M]): La classe du modèle Django.
        hashid (str): L'identifiant hashé.

    Returns:
        Optional[M]: Une instance du modèle si trouvée, sinon None.
    """
    id_ = decode_id(hashid)
    if id_ is None:
        return None
    try:
        return model_class.objects.get(id=id_)
    except model_class.DoesNotExist:
        return None
