from typing import Callable, Any, Optional, Dict

from django.http import HttpResponse, HttpRequest
from functools import wraps
from django.shortcuts import get_object_or_404, render
from epreuve.models import Epreuve, Exercice, MembreComite
from inscription.models import GroupeParticipant
from .interrogations_bd import user_est_inscrit_a_epreuve
from .utils import decode_id


# Décorateur générique pour vérifier l'appartenance de l'utilisateur à un groupe spécifique.
def appartient_au_groupe(group_name):
    """
    Crée un décorateur qui vérifie si l'utilisateur connecté appartient au groupe spécifié.

    Args:
        group_name (str): Le nom du groupe à vérifier.

    Returns:
        Un décorateur qui encapsule la vue et effectue la vérification.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Vérifier si l'utilisateur courant appartient au groupe donné.
            if not request.user.groups.filter(name=group_name).exists():
                # Si l'utilisateur n'appartient pas au groupe, retourner une réponse HTTP "Forbidden".
                context: dict = {'message': "Vous n'avez pas les droits nécessaires pour exécuter cette action."}
                return render(request, 'olympiadesnsi/erreur.html', context, status=403)
            # Si la vérification est passée, continuer à la vue originale.
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


# Décorateurs spécifiques pour chaque rôle.
def organisateur_required(view_func):
    """
    Décorateur spécifique pour vérifier si l'utilisateur est un organisateur.

    Utilise le décorateur 'appartient_au_groupe' avec le nom du groupe 'Organisateur'.
    """
    return appartient_au_groupe('Organisateur')(view_func)


def participant_required(view_func):
    """
    Décorateur spécifique pour vérifier si l'utilisateur est un participant.

    Utilise le décorateur 'appartient_au_groupe' avec le nom du groupe 'Participant'.
    """
    return appartient_au_groupe('Participant')(view_func)


def administrateur_epreuve_required(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Vérifie que l'utilisateur est organisateur et référent de l'épreuve (administrateur).
    L'objet Epreuve est injecté dans `request.epreuve` par `resolve_hashid_param`.
    """

    @wraps(view_func)
    @organisateur_required
    @resolve_hashid_param("hash_epreuve_id", target_name="epreuve_id")  # Injecte dans request.epreuve
    def _wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        # L'objet Epreuve est censé avoir été injecté ici par le décorateur précédent
        epreuve: Optional[Epreuve] = getattr(request, "epreuve", None)

        if epreuve is None:
            context = {'message': "ID de l'épreuve introuvable."}
            return render(request, 'olympiadesnsi/erreur.html', context, status=403)

        id_exercice = kwargs.get("id_exercice", None)
        if id_exercice:
            exercice = get_object_or_404(Exercice, id=id_exercice)
            if not (request.user == epreuve.referent or request.user == exercice.auteur):
                context = {
                    'message': "Vous n'avez pas les droits nécessaires pour cette action réservée à "
                               "l'administrateur de l'épreuve ou au créateur de l'exercice."
                }
                return render(request, 'olympiadesnsi/erreur.html', context, status=403)
            request.exercice = exercice

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def participant_inscrit_a_epreuve_required(view_func):
    """
    Décorateur qui vérifie si l'utilisateur est un participant inscrit à une épreuve spécifique.

    Args:
        view_func: La vue Django à laquelle le décorateur est appliqué.

    Returns:
        La vue modifiée avec les vérifications d'appartenance au groupe des participants
        et d'inscription à l'épreuve.
    """

    @wraps(view_func)
    @participant_required
    @resolve_hashid_param("hash_epreuve_id", target_name="epreuve_id")
    def _wrapped_view(request, *args, **kwargs):
        epreuve = getattr(request, "epreuve", None)
        if epreuve is None:
            return render(request, "olympiadesnsi/erreur.html", {"message": "ID de l'épreuve introuvable."}, status=403)

        if not user_est_inscrit_a_epreuve(request.user, epreuve):
            return render(request, "olympiadesnsi/erreur.html", {
                "message": "Accès refusé car vous n'êtes pas inscrit à l'épreuve concernée."
            }, status=403)

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def administrateur_exercice_required(view_func):
    """
    Décorateur qui vérifie si l'utilisateur est un participant et soit le référent de l'épreuve
    associée à l'exercice, soit l'auteur de l'exercice.

    Args:
        view_func: La vue Django à laquelle le décorateur est appliqué.

    Returns:
        La vue modifiée avec les vérifications nécessaires.
    """
    @wraps(view_func)
    @organisateur_required
    @resolve_hashid_param("hash_epreuve_id", target_name="epreuve_id")
    def _wrapped_view(request, *args, **kwargs):
        epreuve_id = kwargs.get('epreuve_id')
        id_exercice = kwargs.get('id_exercice', None)  # Utilisez 'id_exercice' pour correspondre à la vue
        epreuve: Epreuve = get_object_or_404(Epreuve, id=epreuve_id)
        if id_exercice:
            exercice: Exercice = get_object_or_404(Exercice, id=id_exercice)
            if not (request.user == epreuve.referent or request.user == exercice.auteur):
                context: dict = {'message': "Vous n'avez pas les droits nécessaires pour cette action réservée à "
                                            "l'administrateur de l'épreuve ou au créateur de l'éxercice."}
                return render(request, 'olympiadesnsi/erreur.html', context, status=403)
            request.exercice = exercice

        request.epreuve = epreuve  # Toujours attacher l'épreuve à la requête

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def membre_comite_required(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """
    Décorateur qui vérifie si l'utilisateur est membre du comité d'organisation
    de l'épreuve référencée par son hashid.

    Le décorateur :
    - décode le hashid via `resolve_hashid_param`,
    - injecte l’objet `Epreuve` dans `request.epreuve`,
    - vérifie que l'utilisateur est bien membre du comité de cette épreuve.

    Si l'utilisateur n'est pas membre du comité, une page d'erreur est renvoyée.

    Args:
        view_func: La vue Django à protéger.

    Returns:
        Callable: La vue encapsulée avec les vérifications nécessaires.
    """

    @wraps(view_func)
    @resolve_hashid_param("hash_epreuve_id", target_name="epreuve_id")
    def _wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        epreuve: Optional[Epreuve] = getattr(request, "epreuve", None)
        if epreuve is None:
            return render(request, 'olympiadesnsi/erreur.html',
                          {'message': "ID de l'épreuve introuvable."},
                          status=403)

        # Vérifie si l'utilisateur courant est membre du comité de cette épreuve
        if not MembreComite.objects.filter(membre=request.user, epreuve=epreuve).exists():
            return render(request, 'olympiadesnsi/erreur.html',
                          {'message': "Vous n'avez pas les droits nécessaires pour cette action réservée "
                                      "aux membres du comité d'organisation de l'épreuve."},
                          status=403)

        # Si un id_exercice est présent dans l'URL, on injecte aussi l'exercice dans la requête
        id_exercice = kwargs.get('id_exercice')
        if id_exercice:
            exercice: Exercice = get_object_or_404(Exercice, id=id_exercice)
            request.exercice = exercice

        # Tout est bon, on exécute la vue
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def administrateur_groupe_required(view_func):
    """
    Décorateur qui vérifie si l'utilisateur est un organisateur et l'administrateur d'un groupe spécifique.

    Args:
        view_func (Callable): La fonction de vue à laquelle le décorateur est appliqué.

    Returns:
        Callable: La fonction de vue enveloppée avec les vérifications d'autorisation.
    """

    @wraps(view_func)
    @organisateur_required  # Assurez-vous que c'est bien le bon nom de votre décorateur.
    def _wrapped_view(request, *args, **kwargs):
        # Récupère l'ID du groupe à partir des arguments de la vue.
        groupe_id = kwargs.get('groupe_id')
        if groupe_id:
            # Tente de récupérer le groupe et vérifie si l'utilisateur courant en est l'administrateur.
            try:
                groupe: GroupeParticipant = GroupeParticipant.objects.get(id=groupe_id, referent=request.user)
            except GroupeParticipant.DoesNotExist:
                # Si l'utilisateur n'est pas l'administrateur du groupe, renvoie une réponse interdite.
                context: dict = {'message': "Vous n'avez pas les droits nécessaires pour cette action."}
                return render(request, 'olympiadesnsi/erreur.html', context, status=403)
            # Attache l'objet GroupeParticipant à l'objet request pour éviter une nouvelle requête dans la vue.
            request.groupe = groupe

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def resolve_hashid_param(
        param_name: str,
        target_name: Optional[str] = None,
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    """
    Décorateur qui décode un identifiant hashé contenu dans les paramètres d'URL
    et (optionnellement) réinjecte l'identifiant décodé dans kwargs.

    Exemple :
    - URL: .../<str:hash_epreuve_id>/...
    - @resolve_hashid_param("hash_epreuve_id", target_name="epreuve_id")

    Effets :
    - décode hash_epreuve_id -> int
    - supprime `hash_epreuve_id` de kwargs
    - ajoute `epreuve_id` dans kwargs (si target_name est fourni)
    - si target_name == "epreuve_id", injecte aussi l'objet Epreuve dans request.epreuve
    """

    def decorator(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        def wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            hashid: Optional[str] = kwargs.get(param_name)
            if hashid is None:
                context: Dict[str, str] = {"message": f"Le paramètre '{param_name}' est manquant dans l'URL."}
                return render(request, "olympiadesnsi/erreur.html", context, status=403)

            resolved_id: Optional[int] = decode_id(hashid)
            if resolved_id is None:
                context: Dict[str, str] = {
                    "message": "Identifiant invalide dans l'URL. Veuillez contacter l’administrateur."
                }
                return render(request, "olympiadesnsi/erreur.html", context, status=403)

            # On retire le hashid, pour ne pas polluer la signature de la vue.
            del kwargs[param_name]

            # On injecte l'id décodé dans kwargs si demandé.
            if target_name is not None:
                kwargs[target_name] = resolved_id

            # Cas spécial : si on décode une épreuve, on injecte aussi l'objet.
            if target_name == "epreuve_id":
                request.epreuve = get_object_or_404(Epreuve, id=resolved_id)

            return view_func(request, *args, **kwargs)

        return wraps(view_func)(wrapped_view)

    return decorator
