from typing import Optional, List, TypedDict


class JeuDeTestDict(TypedDict):
    instance: str
    reponse: str


class ExerciceDict(TypedDict, total=False):
    titre: str
    bareme: Optional[int]
    type_exercice: str
    enonce: Optional[str]
    enonce_code: Optional[str]
    avec_jeu_de_test: bool
    separateur_jeu_test: Optional[str]
    separateur_reponse_jeudetest: Optional[str]
    retour_en_direct: bool
    code_a_soumettre: str
    nombre_max_soumissions: int
    jeux_de_test: List[JeuDeTestDict]


class EpreuveDict(TypedDict):
    nom: str
    code: str
    date_debut: str
    date_fin: str
    duree: Optional[int]
    exercices_un_par_un: bool
    temps_limite: bool
    exercices: List[ExerciceDict]