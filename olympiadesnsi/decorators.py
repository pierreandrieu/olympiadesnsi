from django.http import HttpResponseForbidden
from functools import wraps
from django.shortcuts import get_object_or_404
from epreuve.models import Epreuve, Exercice, MembreComite
from inscription.models import GroupeParticipant
from .interrogations_bd import user_est_inscrit_a_epreuve


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
                return HttpResponseForbidden("Accès refusé.")
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


def administrateur_epreuve_required(view_func):
    """
    Décorateur pour vérifier si l'utilisateur est le référent (administrateur) de l'épreuve spécifiée.

    En plus de vérifier l'appartenance au groupe 'Organisateur', ce décorateur vérifie
    si l'utilisateur est le référent de l'épreuve passée en argument dans l'URL.
    """

    @wraps(view_func)
    @organisateur_required  # Réutilise le décorateur 'est_organisateur' pour vérifier le rôle d'organisateur.
    def _wrapped_view(request, *args, **kwargs):
        # Récupérer l'ID de l'épreuve depuis les arguments de la vue.
        epreuve_id = kwargs.get('epreuve_id')
        if epreuve_id:
            # Récupérer l'objet Epreuve correspondant ou retourner une erreur 404 si non trouvé.
            epreuve = get_object_or_404(Epreuve, id=epreuve_id)
            # Vérifier si l'utilisateur est le référent de l'épreuve.
            if request.user != epreuve.referent:
                # Si non, retourner une réponse HTTP "Forbidden".
                return HttpResponseForbidden("Vous n'êtes pas le référent de cette épreuve.")
            # Attacher l'objet Epreuve à l'objet request pour éviter une nouvelle requête dans la vue.
            request.epreuve = epreuve
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
    @participant_required  # Réutilise le décorateur 'est_participant' pour vérifier le rôle de participant.
    def _wrapped_view(request, *args, **kwargs):
        epreuve_id = kwargs.get('epreuve_id')
        if epreuve_id:
            epreuve = get_object_or_404(Epreuve, id=epreuve_id)
            # Réutiliser la logique de la fonction 'user_est_inscrit_a_epreuve'
            if not user_est_inscrit_a_epreuve(request.user, epreuve):
                return HttpResponseForbidden(
                    "Vous n'êtes pas inscrit à cette épreuve ou vous n'appartenez pas au groupe de participants.")
            # Attacher l'objet Epreuve à l'objet request pour éviter une nouvelle requête dans la vue
            request.epreuve = epreuve
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
    def _wrapped_view(request, *args, **kwargs):
        id_exercice = kwargs.get('id_exercice', None)

        if id_exercice:
            exercice = get_object_or_404(Exercice, id=id_exercice)
            epreuve = exercice.epreuve
            if not (request.user == epreuve.referent or request.user == exercice.auteur):
                return HttpResponseForbidden("Vous n'avez pas les droits nécessaires pour cette action.")
            request.exercice = exercice

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def membre_comite_required(view_func):
    """
    Décorateur pour les vues qui vérifie si l'utilisateur courant est membre du comité
    d'organisation de l'épreuve spécifiée par l'argument 'epreuve_id' de la vue.
    Redirige vers une réponse HTTP Forbidden si la condition n'est pas remplie.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Récupère l'ID de l'épreuve à partir des arguments de la vue
        epreuve_id = kwargs.get('epreuve_id')
        if epreuve_id is None:
            # Si l'ID de l'épreuve n'est pas fourni, renvoie une réponse Forbidden
            return HttpResponseForbidden("ID de l'épreuve manquant.")

        # Récupère l'épreuve correspondante ou renvoie une erreur 404 si non trouvée
        epreuve = get_object_or_404(Epreuve, id=epreuve_id)

        # Vérifie si l'utilisateur courant est membre du comité de cette épreuve
        if not MembreComite.objects.filter(membre=request.user, epreuve=epreuve).exists():
            # Si l'utilisateur n'est pas membre du comité, renvoie une réponse Forbidden
            return HttpResponseForbidden("Vous n'avez pas les droits d'accès nécessaires.")

        # Attacher l'objet Epreuve à l'objet request pour éviter une nouvelle requête dans la vue
        request.epreuve = epreuve
        # Si toutes les vérifications sont passées, exécute la vue originale
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
                groupe = GroupeParticipant.objects.get(id=groupe_id, referent=request.user)
            except GroupeParticipant.DoesNotExist:
                # Si l'utilisateur n'est pas l'administrateur du groupe, renvoie une réponse interdite.
                return HttpResponseForbidden("Vous n'avez pas les droits nécessaires pour accéder à cette ressource.")

            # Attache l'objet GroupeParticipant à l'objet request pour éviter une nouvelle requête dans la vue.
            request.groupe = groupe

        return view_func(request, *args, **kwargs)

    return _wrapped_view
