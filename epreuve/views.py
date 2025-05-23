import csv
import io
import logging
import zipfile
from collections import defaultdict
from io import BytesIO, StringIO
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet, Count, Prefetch, Case, When, IntegerField, Value, Q, F, Max
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect, HttpRequest, HttpResponse
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
from django.urls import reverse
from epreuve.models import Epreuve, Exercice, JeuDeTest, MembreComite, UserEpreuve, UserExercice
from epreuve.forms import ExerciceForm, AjoutOrganisateurForm
from epreuve.utils import temps_restant_seconde, vider_jeux_test_exercice, \
    analyse_reponse_jeu_de_test
from inscription.models import GroupeParticipeAEpreuve, GroupeParticipant
import olympiadesnsi.decorators as decorators
import json
from typing import List, Optional, Dict, Set, Tuple, cast, Any, Union

from olympiadesnsi.constants import MAX_CODE_LENGTH, MAX_REPONSE_LENGTH
from olympiadesnsi.utils import encode_id

logger = logging.getLogger(__name__)


@csrf_protect
@login_required
@decorators.participant_inscrit_a_epreuve_required
@ratelimit(key='user', rate='10/m', block=True)
@ratelimit(key='user', rate='2/s', block=True)
def soumettre(request: HttpRequest, epreuve_id=None) -> Union[JsonResponse, HttpResponseRedirect, HttpResponse]:
    """
    Gère la soumission d'une réponse à un exercice par un participant.

    Cette vue vérifie les conditions de soumission (méthode POST, limites de taux),
    traite les données soumises, met à jour les enregistrements correspondants,
    et renvoie une réponse JSON avec le statut de la soumission.

    Args:
        request (HttpRequest): La requête HTTP contenant les données de soumission.
        epreuve_id (int): l'id de l'épreuve
    Returns:
        JsonResponse: Réponse JSON contenant le statut de la soumission et les données mises à jour.
        HttpResponseRedirect: Redirection en cas d'erreur ou de fin d'épreuve.

    Raises:
        json.JSONDecodeError: Si les données POST ne sont pas un JSON valide.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=405)

    try:

        # Extraction et validation des données de la requête
        data: Dict[str, Any] = json.loads(request.body)
        exercice_id: int = data.get('exercice_id')
        code_soumis: str = data.get('code_soumis', "")
        code_soumis = code_soumis.replace('\u00A0', ' ').replace('\u200B', '').replace('\t', '    ')

        solution_instance: str = data.get('solution_instance', "")

        if len(code_soumis) > MAX_CODE_LENGTH or len(solution_instance) > MAX_REPONSE_LENGTH:
            context = {'message': "La taille des données envoyées est trop importante."}
            return render(request, 'olympiadesnsi/erreur.html', context, status=413)
        # Récupération de l'exercice
        try:
            exercice: Exercice = Exercice.objects.get(id=exercice_id)
        except Exercice.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Exercice introuvable'}, status=404)

        # Récupération de l'épreuve associée
        epreuve: Epreuve = exercice.epreuve

        # Vérification de l'état de l'épreuve
        if epreuve.pas_commencee() or epreuve.est_close():
            return redirect(reverse('afficher_epreuve', kwargs={'hash_epreuve_id': encode_id(epreuve.id)}))

        # Gestion du temps limite de l'épreuve
        if epreuve.temps_limite:
            user_epreuve: UserEpreuve = UserEpreuve.objects.get(participant=request.user, epreuve=epreuve)
            if not user_epreuve.debut_epreuve:
                user_epreuve.debut_epreuve = timezone.now()
                user_epreuve.save()

            temps_restant: int = temps_restant_seconde(user_epreuve, epreuve)
            if temps_restant < 1:
                return redirect(reverse('afficher_epreuve', kwargs={'hash_epreuve_id': encode_id(epreuve.id)}))

        # Récupération ou création de l'association UserExercice
        user_exercice: UserExercice = UserExercice.objects.get(participant=request.user, exercice=exercice)

        # Vérification du nombre de soumissions
        if user_exercice.nb_soumissions >= exercice.nombre_max_soumissions:
            return JsonResponse({'success': False, 'error': 'Nombre maximum de soumissions atteint'}, status=403)

        # Mise à jour des données de soumission
        user_exercice.code_participant = code_soumis
        user_exercice.solution_instance_participant = solution_instance
        user_exercice.nb_soumissions += 1
        user_exercice.save()

        # Traitement spécifique pour les exercices sans jeu de test
        if not exercice.avec_jeu_de_test:
            return JsonResponse({
                'success': True,
                'nb_soumissions_restantes': exercice.nombre_max_soumissions - user_exercice.nb_soumissions,
                'code_enregistre': user_exercice.code_participant,
                'reponse_jeu_de_test_enregistree': user_exercice.solution_instance_participant
            })

        # Vérification de la solution pour les exercices avec jeu de test
        jeu_de_test: Optional[JeuDeTest] = user_exercice.jeu_de_test
        reponse_valide: bool = (jeu_de_test is not None and analyse_reponse_jeu_de_test(solution_instance, jeu_de_test.reponse))

        return JsonResponse({
            'success': True,
            'reponse_valide': reponse_valide,
            'nb_soumissions_restantes': exercice.nombre_max_soumissions - user_exercice.nb_soumissions,
            'code_enregistre': user_exercice.code_participant,
            'reponse_jeu_de_test_enregistree': user_exercice.solution_instance_participant,
            'code_requis': exercice.code_a_soumettre != 'aucun',
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Données invalides'}, status=400)


@login_required
@decorators.participant_inscrit_a_epreuve_required
def detail_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    epreuve: Epreuve = getattr(request, 'epreuve', None)
    indication_utilisateurs_retour: int = 0
    anonymats = ["", "", ""]  # Valeurs par défaut
    user_epreuve: Optional[UserEpreuve] = None

    if epreuve:
        exercices: QuerySet[Exercice] = epreuve.get_exercices()
        for exercice in exercices:
            if exercice.avec_jeu_de_test and exercice.retour_en_direct:
                indication_utilisateurs_retour += 1

        # Récupération ou création de l'entrée `UserEpreuve`
        user_epreuve, _ = UserEpreuve.objects.get_or_create(participant=request.user, epreuve=epreuve)
        anonymats = user_epreuve.get_anonymat()

    if request.method == "POST":
        # Récupération des choix de l'utilisateur
        anonymats = []
        for i in range(1, 4):
            choix = request.POST.get(f"choix_{i}")
            if choix == "1":  # Numéro d'anonymat fourni
                anonymat = request.POST.get(f"anonymat_{i}", "").strip()
                anonymats.append(anonymat if anonymat else "?")
            elif choix == "2":  # Pas de numéro mais a participé
                anonymats.append("?")
            elif choix == "3":  # N'a pas participé
                anonymats.append("-")
            else:
                anonymats.append(";")

        # Sauvegarde en base de données
        if user_epreuve:
            user_epreuve.set_anonymat(anonymats)

        return redirect('afficher_epreuve', hash_epreuve_id=encode_id(epreuve.id))
    return render(request, "epreuve/detail_epreuve.html", {
        "epreuve": epreuve,
        "indication_utilisateurs_retour": indication_utilisateurs_retour,
        "anonymats": anonymats
    })


@login_required
@decorators.participant_inscrit_a_epreuve_required
def afficher_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    """
    Affiche les détails d'une épreuve pour un participant inscrit, incluant les exercices associés
    et le temps restant si l'épreuve est limitée dans le temps.

    La fonction filtre les exercices en fonction du mode de l'épreuve (tous les exercices ou un par un)
    et prépare les données pour affichage dans un format JSON utilisé par le frontend.

    Args:
        request (HttpRequest): La requête HTTP reçue.
        epreuve_id (int): L'identifiant de l'épreuve concernée.

    Returns:
        HttpResponse: La réponse HTTP avec le rendu du template `afficher_epreuve.html`.
    """
    # Récupération de l'utilisateur connecté et de l'épreuve depuis le décorateur.
    user: User = cast(User, request.user)

    epreuve: Optional[Epreuve] = getattr(request, 'epreuve', None)
    url_soumission = reverse("soumettre", kwargs={"hash_epreuve_id": encode_id(epreuve.id)})

    if epreuve.pas_commencee():
        return render(request, 'epreuve/erreurs/epreuve_pas_encore_ouverte.html')

    if epreuve.est_close():
        return render(request, 'epreuve/erreurs/epreuve_terminee.html')

    # Calcul du temps restant pour compléter l'épreuve, si applicable.
    temps_restant: Optional[int] = None
    if epreuve and epreuve.temps_limite:
        user_epreuve, _ = UserEpreuve.objects.get_or_create(participant=user, epreuve=epreuve)
        if not user_epreuve.debut_epreuve:
            # Convertit la durée de l'épreuve en minutes en un objet timedelta
            user_epreuve.debut_epreuve = timezone.now()
            user_epreuve.save()

        # Calcul du temps restant
        temps_restant = temps_restant_seconde(user_epreuve, epreuve)
        if temps_restant < 1:
            return render(request, 'epreuve/erreurs/temps_ecoule.html')

    # Sélection de tous les exercices associés à l'épreuve, ordonnés par leur numéro.
    exercices: List[Exercice] = list(Exercice.objects.filter(epreuve=epreuve).order_by('numero'))
    exercice_a_traiter_si_un_par_un: Optional[Exercice] = None
    for exercice in exercices:
        user_exercice, _ = UserExercice.objects.get_or_create(exercice=exercice, participant=user)
        if not user_exercice.solution_instance_participant or not user_exercice.code_participant:
            exercice_a_traiter_si_un_par_un = exercice
        if exercice.avec_jeu_de_test and not user_exercice.jeu_de_test:
            user_exercice.jeu_de_test = exercice.pick_jeu_de_test()
            user_exercice.save()

    # Si l'épreuve impose de passer les exercices un par un, filtrer pour ne garder que le premier non complété.
    if epreuve and epreuve.exercices_un_par_un:
        exercices = [exercice_a_traiter_si_un_par_un]

    # Préparation des données des exercices pour le frontend.
    exercices_json_list: List[Dict[str, object]] = []
    for ex in exercices:
        user_exercice, _ = UserExercice.objects.get_or_create(exercice=ex, participant=user)
        jeu_de_test: Optional[JeuDeTest] = user_exercice.jeu_de_test

        exercice_dict: Dict[str, object] = {
            'id': ex.id,
            'titre': ex.titre,
            'bareme': ex.bareme,
            'enonce': ex.enonce,
            'enonce_code': ex.enonce_code,
            'type_exercice': ex.type_exercice,
            'avec_jeu_de_test': ex.avec_jeu_de_test,
            'reponse_jeu_de_test_enregistree': user_exercice.solution_instance_participant,
            'code_enregistre': user_exercice.code_participant,
            'code_a_soumettre': ex.code_a_soumettre,
            'nb_soumissions_restantes': ex.nombre_max_soumissions - user_exercice.nb_soumissions,
            'nb_max_soumissions': ex.nombre_max_soumissions,
            'retour_en_direct': ex.retour_en_direct,
            'instance_de_test': jeu_de_test.instance if jeu_de_test else "",
            'reponse_valide': str(user_exercice.solution_instance_participant).split() == (
                str(jeu_de_test.reponse).split() if jeu_de_test else ""),
            "lecture_seule": False,
        }

        exercices_json_list.append(exercice_dict)

    # Conversion des données des exercices en JSON pour utilisation côté client.
    exercices_json: str = json.dumps(exercices_json_list)
    return render(request, 'epreuve/afficher_epreuve.html', {
        'epreuve': epreuve,
        'exercices_json': exercices_json,
        'temps_restant': temps_restant,
        'url': url_soumission,
        "template_base": "olympiadesnsi/base_participant.html",
    })



@login_required
@decorators.administrateur_epreuve_required
def supprimer_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    epreuve: Epreuve = getattr(request, 'epreuve', None)
    if request.method == "POST":
        epreuve.delete()
        return redirect('espace_organisateur')
    return redirect('espace_organisateur')



@login_required
@decorators.membre_comite_required
def visualiser_epreuve_organisateur(request, epreuve_id):
    epreuve: Epreuve = getattr(request, 'epreuve', None)
    # Calcul du temps restant pour compléter l'épreuve, si applicable.
    temps_restant_secondes: Optional[int] = None
    if epreuve and epreuve.temps_limite:
        temps_restant_secondes = epreuve.duree * 60

    # Sélection de tous les exercices associés à l'épreuve, ordonnés par leur numéro.
    exercices: List[Exercice] = list(Exercice.objects.filter(epreuve=epreuve).order_by('numero'))

    exercices_json_list: List[Dict[str, object]] = []
    for ex in exercices:
        jeu_de_test: Optional[JeuDeTest] = None
        if ex.avec_jeu_de_test:
            jeu_de_test = ex.pick_jeu_de_test()

        exercice_dict: Dict[str, object] = {
            'id': ex.id,
            'titre': ex.titre,
            'bareme': ex.bareme,
            'enonce': ex.enonce,
            'enonce_code': ex.enonce_code,
            'type_exercice': ex.type_exercice,
            'avec_jeu_de_test': ex.avec_jeu_de_test,
            'reponse_jeu_de_test_enregistree': "reponse_eleve",
            'code_enregistre': "code_eleve",
            'code_a_soumettre': ex.code_a_soumettre,
            'nb_soumissions_restantes': ex.nombre_max_soumissions,
            'nb_max_soumissions': ex.nombre_max_soumissions,
            'retour_en_direct': ex.retour_en_direct,
            'instance_de_test': jeu_de_test.instance if jeu_de_test else "",
            'reponse_valide': False,
            'reponse_attendue': jeu_de_test.reponse if jeu_de_test else "",
        }

        exercices_json_list.append(exercice_dict)

    # Conversion des données des exercices en JSON pour utilisation côté client.
    exercices_json: str = json.dumps(exercices_json_list)
    return render(request, 'epreuve/afficher_epreuve.html', {
        'epreuve': epreuve,
        'exercices_json': exercices_json,
        'temps_restant': temps_restant_secondes,
        "lecture_seule": True,
        "template_base": "olympiadesnsi/base_organisateur.html",
    })



@login_required
@decorators.administrateur_epreuve_required
def ajouter_organisateur(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    """
    Vue pour ajouter un organisateur au comité d'organisation d'une épreuve.

    Cette vue permet à un administrateur d'épreuve d'ajouter un nouvel utilisateur
    au comité de l'épreuve spécifiée, si cet utilisateur :
      - existe,
      - n’est pas déjà dans le comité,
      - n’est pas le référent de l’épreuve.

    L'objet `epreuve` est injecté dynamiquement dans `request` par le décorateur
    `@administrateur_epreuve_required`.

    Args:
        request (HttpRequest): Requête HTTP reçue.
        epreuve_id (int): Identifiant de l'épreuve concernée (non utilisé ici car injecté par décorateur).

    Returns:
        HttpResponse: Redirection en cas de succès, ou rendu du template avec erreurs sinon.
    """
    # L'objet épreuve est garanti par le décorateur, on l’extrait via `getattr`
    epreuve: Epreuve = getattr(request, 'epreuve')

    # Initialisation du formulaire (lié ou non à POST)
    form: AjoutOrganisateurForm = AjoutOrganisateurForm(
        data=request.POST or None,
        epreuve=epreuve,
        request_user=request.user
    )

    if request.method == "POST" and form.is_valid():
        # Récupération du nom d'utilisateur validé (garanti existant et admissible)
        username: str = form.cleaned_data['username']
        user_to_add: User = User.objects.get(username=username)

        # Ajout au comité
        MembreComite.objects.create(epreuve=epreuve, membre=user_to_add)

        # Message de confirmation
        messages.success(
            request,
            f"{username} a bien été ajouté au comité d'organisation de l'épreuve « {epreuve.nom} »."
        )

        # Redirection vers la page d’espace organisateur
        return HttpResponseRedirect(reverse('espace_organisateur'))
    if not form.is_valid():
        username_errors = form.errors.get('username')
        if username_errors:
            messages.error(request, username_errors[0])
    return redirect('espace_organisateur')


@login_required
@decorators.administrateur_epreuve_required
def retirer_organisateur(request: HttpRequest, epreuve_id: int, user_id: int) -> HttpResponse:
    """
    Supprime un membre du comité d'organisation d'une épreuve.

    Cette action est strictement réservée au référent de l'épreuve. Le référent
    ne peut pas se retirer lui-même via cette vue.

    Args:
        request (HttpRequest): L'objet de la requête HTTP.
        epreuve_id (int): L'identifiant entier de l'épreuve (décodé depuis le hash).
        user_id (int): L'identifiant du membre à retirer.

    Returns:
        HttpResponse: Une redirection vers l'espace organisateur avec un message.
    """
    # Récupère l'objet Epreuve depuis le décorateur
    epreuve: Epreuve = getattr(request, 'epreuve', None)  # Épreuve récupérée par le décorateur.

    # Récupère l'utilisateur à supprimer
    utilisateur: User = get_object_or_404(User, id=user_id)

    # Interdit de retirer le référent lui-même
    if utilisateur == epreuve.referent:
        messages.error(request, "Le référent ne peut pas se retirer lui-même.")
        return redirect("espace_organisateur")

    # Vérifie s'il est bien membre du comité
    membre = MembreComite.objects.filter(epreuve=epreuve, membre=utilisateur).first()
    if membre:
        membre.delete()
        messages.success(request, f"{utilisateur.username} a été retiré du comité d'organisation.")
    else:
        messages.warning(request, f"{utilisateur.username} ne fait pas partie du comité.")

    return redirect("espace_organisateur")


@login_required
@decorators.membre_comite_required
def inscrire_groupes_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    """
    Inscrit des groupes de participants à une épreuve donnée, en vérifiant que l'utilisateur est un administrateur
    de l'épreuve. Cette vue permet de sélectionner plusieurs groupes pour les inscrire à une épreuve spécifique.

    Args:
        request (HttpRequest): L'objet requête HTTP.
        epreuve_id (int): L'ID de l'épreuve à laquelle les groupes seront inscrits.

    Returns:
        HttpResponse: L'objet réponse HTTP pour rediriger ou afficher la page.
    """
    epreuve: Epreuve = getattr(request, 'epreuve', None)  # Épreuve récupérée par le décorateur.
    logger.debug("epreuve pour inscription : ", epreuve)

    if request.method == 'POST':
        # IDs des groupes sélectionnés pour l'inscription.
        groupe_ids: List[str] = request.POST.getlist(key='groups', default=[])
        logger.debug("id des groupes a inscrire : ", groupe_ids)
        with transaction.atomic():
            for groupe_id in groupe_ids:
                groupe: GroupeParticipant = get_object_or_404(GroupeParticipant, id=groupe_id)
                epreuve.inscrire_groupe(groupe)
                if epreuve.annale:
                    epreuve.annale.inscrire_groupe(groupe)

            messages.success(request, "Les groupes et leurs membres ont été inscrits avec succès à l'épreuve.")
            return redirect('espace_organisateur')
    else:
        # Récupère les groupes non encore inscrits à cette épreuve pour les afficher dans le formulaire.
        groupes_inscrits_ids: List[int] = list(GroupeParticipeAEpreuve.objects.filter(
            epreuve=epreuve).values_list('groupe__id', flat=True))
        groupes_non_inscrits: QuerySet[GroupeParticipant] = (
            GroupeParticipant.objects.filter(referent=request.user, statut="VALIDE").exclude(id__in=groupes_inscrits_ids))

    return render(request, 'epreuve/inscrire_groupes_epreuve.html',
                  {'epreuve': epreuve, 'groupes': groupes_non_inscrits})


@login_required
@decorators.membre_comite_required
@decorators.resolve_hashid_param("groupe_hashid", target_name="groupe_id")
def desinscrire_groupe_epreuve(request: HttpRequest, epreuve_id: int, groupe_id: int) -> HttpResponse:
    """
    Désinscrit tous les participants d'un groupe spécifique d'une épreuve donnée.

    Cette fonction supprime toutes les entrées liées dans `UserExercice` pour chaque participant
    et chaque exercice associé à l'épreuve, puis supprime les entrées `UserEpreuve` qui lient
    les participants à l'épreuve.

    Args:
        request (HttpRequest): L'objet requête HTTP.
        groupe_id (int): L'ID du groupe à désinscrire.
        epreuve_id (int): L'ID de l'épreuve de laquelle les participants seront désinscrits.

    Returns:
        HttpResponse: Redirige vers l'espace organisateur avec un message de succès.
    """

    # Récupération de l'épreuve à partir de son ID
    epreuve: Epreuve = get_object_or_404(Epreuve, pk=epreuve_id)
    # Récupération du groupe à désinscrire à partir de son ID
    groupe: GroupeParticipant = get_object_or_404(GroupeParticipant, pk=groupe_id)
    # Récupération de l'association entre groupe et épreuve
    groupe_participe_a_epreuve: GroupeParticipeAEpreuve = get_object_or_404(GroupeParticipeAEpreuve,
                                                                            groupe=groupe,
                                                                            epreuve=epreuve)
    with transaction.atomic():
        participants: QuerySet[User] = groupe.participants()

        # Récupérer tous les UserEpreuve pour l'épreuve et le groupe spécifiés
        user_epreuves = UserEpreuve.objects.filter(epreuve=epreuve, participant__in=participants)

        # Récupérer les IDs de tous les exercices associés à l'épreuve
        exercices_ids: List[int] = list(epreuve.exercices.values_list('id', flat=True))

        # Supprimer tous les UserExercice associés aux participants de l'épreuve et du groupe
        UserExercice.objects.filter(exercice_id__in=exercices_ids,
                                    participant__in=user_epreuves.values_list('participant', flat=True)).delete()

        # Suppression des entrées UserEpreuve pour finaliser la désinscription
        user_epreuves.delete()

        groupe_participe_a_epreuve.delete()

        # Affichage d'un message de succès et redirection
        messages.success(request,
                         f"Les membres du groupe {groupe.nom} ont été désinscrits de l'épreuve {epreuve.nom}.")
        return redirect('espace_organisateur')


@login_required
@decorators.resolve_hashid_param("hash_exercice_id", target_name="id_exercice")
@decorators.membre_comite_required
def supprimer_exercice(request: HttpRequest, epreuve_id: int, id_exercice: int) -> HttpResponse:
    """
    Supprime un exercice spécifique et affiche un message de succès.

    Cette vue est accessible uniquement aux utilisateurs qui ont les droits nécessaires sur
    l'exercice, vérifiés par le décorateur 'administrateur_exercice_required'. L'exercice à supprimer
    est identifié par son ID et est récupéré automatiquement par le décorateur.

    Args:
        request (HttpRequest): L'objet HttpRequest.
        id_exercice (int): L'identifiant de l'exercice à supprimer.

    Returns:
        HttpResponse: Redirige vers l'espace organisateur après la suppression de l'exercice.
    """
    # L'objet exercice est récupéré par le décorateur 'administrateur_exercice_required'
    exercice: Exercice = getattr(request, 'exercice', None)

    # Sauvegarde le titre et le nom de l'épreuve avant la suppression pour l'utiliser dans le message
    titre_exercice: str = exercice.titre
    nom_epreuve: str = exercice.epreuve.nom

    # Procède à la suppression de l'exercice
    exercice.delete()

    # Affiche un message de succès incluant le titre de l'exercice et le nom de l'épreuve
    messages.success(request, f"L'exercice '{titre_exercice}' de l'épreuve '{nom_epreuve}' a été supprimé.")

    # Redirige vers l'espace organisateur après la suppression
    return redirect('espace_organisateur')


@login_required
@decorators.resolve_hashid_param("hash_exercice_id", target_name="id_exercice")
@decorators.membre_comite_required
def supprimer_jeux_de_test(request: HttpRequest, epreuve_id: int, id_exercice: int) -> HttpResponse:
    """
    Supprime tous les jeux de test associés à un exercice spécifique.

    Cette vue est protégée par deux décorateurs qui garantissent que l'utilisateur est connecté
    et qu'il a les droits d'administrateur sur l'exercice concerné (soit en étant le référent
    de l'épreuve associée, soit l'auteur de l'exercice).

    Args:
        request (HttpRequest): L'objet HttpRequest.
        id_exercice (int): L'identifiant de l'exercice dont les jeux de test doivent être supprimés.

    Returns:
        HttpResponse: Redirige vers la vue d'édition de l'exercice après la suppression des jeux de test.
    """

    # Récupère tous les jeux de test associés à l'exercice spécifié par son ID
    jdts = JeuDeTest.objects.filter(exercice_id=id_exercice)

    # Parcourt chaque jeu de test et le supprime
    for jdt in jdts:
        jdt.delete()

    # Après la suppression, redirige vers la vue d'édition de l'exercice pour refléter les changements
    return redirect('editer_exercice',
                    hash_epreuve_id=encode_id(epreuve_id),
                    exercice_hashid=encode_id(id_exercice))

@login_required
@decorators.membre_comite_required
def creer_exercice(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    return _creer_ou_editer_exercice(request, request.epreuve)


@login_required
@decorators.membre_comite_required
@decorators.resolve_hashid_param("exercice_hashid", target_name="id_exercice")
def editer_exercice(request: HttpRequest, epreuve_id: int, id_exercice: int) -> HttpResponse:
    exercice = get_object_or_404(Exercice, id=id_exercice)
    return _creer_ou_editer_exercice(request, request.epreuve, exercice)


def _creer_ou_editer_exercice(
        request: HttpRequest,
        epreuve: Epreuve,
        exercice: Optional[Exercice] = None
) -> HttpResponse:
    """
    Vue pour créer ou éditer un exercice dans une épreuve.

    Si un exercice est fourni, on est en mode édition. Sinon, on crée un nouvel exercice.

    Args:
        request (HttpRequest): L'objet requête.
        epreuve (Epreuve): L'épreuve concernée.
        exercice (Optional[Exercice]): L'exercice à éditer, ou None si création.

    Returns:
        HttpResponse: La page de formulaire.
    """

    jeux_de_test_str, resultats_jeux_de_test_str = "", ""
    jdt_anciens: Set[Tuple[str, str]] = set()
    jeux_de_test = JeuDeTest.objects.none()

    if exercice and exercice.avec_jeu_de_test:
        jeux_de_test = JeuDeTest.objects.filter(exercice=exercice)
        jeux_de_test_str = exercice.separateur_jeu_test_effectif.join(jeu.instance for jeu in jeux_de_test)
        resultats_jeux_de_test_str = exercice.separateur_reponse_jeudetest_effectif.join(
            jeu.reponse for jeu in jeux_de_test)

    if request.method == 'POST':
        post_data = request.POST.copy()
        # Normalisation des séparateurs
        post_data['separateur_jeux_de_test'] = post_data.get('separateur_jeux_de_test', '').replace('\\n', '\n')
        post_data['separateur_resultats_jeux_de_test'] = post_data.get('separateur_resultats_jeux_de_test', '').replace(
            '\\n', '\n')

        form = ExerciceForm(post_data, instance=exercice, initial={
            'jeux_de_test': jeux_de_test_str,
            'resultats_jeux_de_test': resultats_jeux_de_test_str,
            'separateur_jeux_de_test': post_data['separateur_jeux_de_test'],
            'separateur_resultats_jeux_de_test': post_data['separateur_resultats_jeux_de_test'],
        })

        if form.is_valid():
            exercice = form.save(commit=False)
            exercice.epreuve = epreuve
            action = "mis à jour"

            if not exercice.pk:  # cas création
                exercice.auteur = request.user
                action = "créé"
            exercice.separateur_jeu_test = post_data['separateur_jeux_de_test'] or '\n'
            exercice.separateur_reponse_jeudetest = post_data['separateur_resultats_jeux_de_test'] or '\n'
            exercice.save()
            if action == "créé":
                exercice.inscrire_utilisateurs_de_epreuve()

            # Traitement des jeux de test si activés
            if form.cleaned_data.get('avec_jeu_de_test'):
                nouveaux_jdt: Set[Tuple[str, str]] = set()
                jeux = form.cleaned_data.get('jeux_de_test', '').split(exercice.separateur_jeu_test_effectif)
                resultats = form.cleaned_data.get('resultats_jeux_de_test', '').split(
                    exercice.separateur_reponse_jeudetest_effectif)

                for jeu in jeux_de_test:
                    jdt_anciens.add((jeu.instance, jeu.reponse))

                for jeu, res in zip(jeux, resultats):
                    jeu_tuple = (jeu.strip(), res.strip())
                    if all(jeu_tuple) and jeu_tuple not in jdt_anciens:
                        JeuDeTest.objects.create(exercice=exercice, instance=jeu_tuple[0], reponse=jeu_tuple[1])
                    nouveaux_jdt.add(jeu_tuple)

                for jeu in jeux_de_test:
                    if (jeu.instance.strip(), jeu.reponse.strip()) not in nouveaux_jdt:
                        jeu.delete()
            else:
                vider_jeux_test_exercice(exercice)
            exercice.assigner_jeux_de_test()
            messages.success(request,
                             f"L'exercice {exercice.titre} a été {action} avec succès pour l'épreuve {epreuve.nom}.")
            return redirect('espace_organisateur')

    else:
        form = ExerciceForm(instance=exercice, initial={
            'jeux_de_test': jeux_de_test_str,
            'resultats_jeux_de_test': resultats_jeux_de_test_str,
            'separateur_jeux_de_test': exercice.separateur_jeu_test_effectif.replace("\n",
                                                                                     "\\n") if exercice else "\\n",
            'separateur_resultats_jeux_de_test': exercice.separateur_reponse_jeudetest_effectif.replace("\n",
                                                                                                        "\\n") if exercice else "\\n",
        })

    champs_invisibles = ['jeux_de_test', 'resultats_jeux_de_test', 'retour_en_direct']
    champs_visibles = [field.name for field in form.visible_fields() if field.name not in champs_invisibles]

    return render(request, 'epreuve/creer_exercice.html', {
        'form': form,
        'champs_visibles': champs_visibles,
        'champs_invisibles': champs_invisibles,
        'epreuve': epreuve,
        'exercice_id': exercice.id if exercice else None,
        'jeux_de_test': jeux_de_test_str,
        'resultats_jeux_de_test': resultats_jeux_de_test_str,
        'separateur_jeux_de_test': form.initial['separateur_jeux_de_test'],
        'separateur_resultats_jeux_de_test': form.initial['separateur_resultats_jeux_de_test'],
    })


@login_required
@decorators.membre_comite_required
def rendus_participants(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    epreuve: Epreuve = getattr(request, 'epreuve', None)  # Épreuve récupérée par le décorateur.

    exercices = epreuve.exercices.prefetch_related(
        'jeudetest_set',
        Prefetch('user_exercices', queryset=UserExercice.objects.select_related('participant', 'jeu_de_test'))
    ).all()

    # Récupération des UserExercice avec les informations nécessaires
    user_exercices: QuerySet[UserExercice] = UserExercice.objects.filter(
        exercice__epreuve=epreuve,
        exercice__avec_jeu_de_test=True
    ).select_related('jeu_de_test')

    au_moins_un_exo_avec_jeu_test: bool = False

    # Création d'un dictionnaire pour compter les bonnes réponses pour chaque participant
    bonnes_reponses_par_participant = defaultdict(int)
    for ue in user_exercices:
        if ue.exercice.avec_jeu_de_test:
            au_moins_un_exo_avec_jeu_test = True
            if ue.solution_instance_participant:
                if analyse_reponse_jeu_de_test(ue.solution_instance_participant, ue.jeu_de_test.reponse):
                    bonnes_reponses_par_participant[ue.participant_id] += 1

    # Ajout des informations de bonnes réponses aux participants
    participants: QuerySet[User] = User.objects.filter(
        user_epreuves__epreuve=epreuve
    ).distinct().annotate(
        debut_epreuve=F('user_epreuves__debut_epreuve'),
        groupe_id=Max('appartenances__groupe_id'),
        bonnes_reponses=Case(
            *[When(id=k, then=Value(v)) for k, v in bonnes_reponses_par_participant.items()],
            default=Value(0),
            output_field=IntegerField()
        )
    )

    # Statistiques
    total_inscrits = UserEpreuve.objects.filter(epreuve=epreuve).count()
    total_participants = UserEpreuve.objects.filter(epreuve=epreuve, debut_epreuve__isnull=False).count()

    # Statistiques des groupes (si applicable)
    groupes = GroupeParticipant.objects.filter(epreuves=epreuve)
    total_groupes_inscrits = groupes.count()
    total_groupes_avec_participation: int = groupes.annotate(
        debut_non_null=Count(
            'membres__utilisateur__user_epreuves',
            # Correct si 'user_epreuves' est le related_name dans User pour UserEpreuve
            filter=Q(membres__utilisateur__user_epreuves__debut_epreuve__isnull=False,
                     membres__utilisateur__user_epreuves__epreuve=epreuve)
        )
    ).filter(debut_non_null__gt=0).count()

    data_for_js = [
        {
            'exerciceId': ue.exercice.id,
            'exerciceTitre': ue.exercice.titre,
            'participantId': ue.participant.id,
            'username': ue.participant.username,
            'solution': ue.solution_instance_participant if ue.solution_instance_participant else "N/A",
            'expected': ue.jeu_de_test.reponse if ue.jeu_de_test else "N/A",
            'code': ue.code_participant if ue.code_participant else "N/A",
            'test': ue.jeu_de_test.instance if ue.jeu_de_test else "N/A"
        }
        for ue in user_exercices
    ]
    context = {
        'epreuve': epreuve,
        'exercices': exercices,
        'participants': participants,
        'total_inscrits': total_inscrits,
        'total_participants': total_participants,
        'total_groupes_inscrits': total_groupes_inscrits,
        'au_moins_un_exo_avec_jeu_test': au_moins_un_exo_avec_jeu_test,
        'total_groupes_avec_participation': total_groupes_avec_participation,
        'data_for_js': data_for_js
    }

    return render(request, 'epreuve/rendus_participants.html', context)


@login_required
@decorators.membre_comite_required
def export_data(request, epreuve_id: int, by: str) -> HttpResponse:
    """
    Génère et retourne une archive zip des données des utilisateurs, organisées par exercice ou par participant,
    pour une épreuve donnée.

    Args:
        request (HttpRequest): L'objet HttpRequest.
        epreuve_id (int): ID de l'épreuve pour laquelle les données doivent être exportées.
        by (str): Critère d'organisation de l'exportation ('exercice' ou 'participant').

    Returns:
        HttpResponse: Une réponse HTTP avec l'archive zip en pièce jointe.
    """
    epreuve: Epreuve = getattr(request, 'epreuve', None)  # Épreuve récupérée par le décorateur.

    user_exercices = (UserExercice.objects.filter(exercice__epreuve=epreuve).
                      select_related('exercice', 'participant', 'jeu_de_test'))

    user_epreuves = UserEpreuve.objects.filter(epreuve=epreuve).select_related('participant')

    # Calculer les bonnes réponses
    bonnes_reponses_dict = {}
    for ue in user_exercices:
        # Comparaison en tenant compte de strip()
        is_correct = analyse_reponse_jeu_de_test(ue.solution_instance_participant, ue.jeu_de_test.reponse) if ue.jeu_de_test and ue.solution_instance_participant else False
        bonnes_reponses_dict.setdefault(ue.participant.username, 0)
        if is_correct:
            bonnes_reponses_dict[ue.participant.username] += 1

    # Préparation du fichier CSV
    csv_output = StringIO()
    writer = csv.writer(csv_output, delimiter='\t')
    writer.writerow(['username', 'date/heure de debut', 'nombre de bonnes reponses'])

    for user_epreuve in UserEpreuve.objects.filter(epreuve=epreuve).select_related('participant'):
        username = user_epreuve.participant.username
        debut = user_epreuve.debut_epreuve.strftime('%Y-%m-%d %H:%M:%S') if user_epreuve.debut_epreuve else 'N/A'
        bonnes_reponses = bonnes_reponses_dict.get(username, 0)
        writer.writerow([username, debut, bonnes_reponses])

    au_moins_un_exo_avec_jeu_test: bool = False

    # Création d'un dictionnaire pour compter les bonnes réponses pour chaque participant
    bonnes_reponses_par_participant = defaultdict(int)
    for ue in user_exercices:
        if ue.exercice.avec_jeu_de_test:
            au_moins_un_exo_avec_jeu_test = True
            if ue.solution_instance_participant:
                if analyse_reponse_jeu_de_test(ue.solution_instance_participant, ue.jeu_de_test.reponse):
                    bonnes_reponses_par_participant[ue.participant_id] += 1

    # Ajout des informations de bonnes réponses aux participants
    participants: QuerySet[User] = User.objects.filter(
        user_epreuves__epreuve=epreuve
    ).distinct().annotate(
        bonnes_reponses=Case(
            *[When(id=k, then=Value(v)) for k, v in bonnes_reponses_par_participant.items()],
            default=Value(0),
            output_field=IntegerField()
        )
    )

    # Création du fichier zip en mémoire
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr('resume_epreuve.tsv', csv_output.getvalue())
        if by == 'exercice':
            for exercice in epreuve.exercices.all().prefetch_related('user_exercices'):
                for user_exercice in exercice.user_exercices.all():
                    user = user_exercice.participant
                    nom_participant: str = user.username
                    exercice_titre: str = exercice.titre
                    exercice_id: int = exercice.id
                    user_folder = f"{exercice_titre}/{nom_participant}"
                    if exercice.avec_jeu_de_test:
                        solution = user_exercice.solution_instance_participant.strip() if user_exercice.solution_instance_participant else ""
                        expected = user_exercice.jeu_de_test.reponse.strip() if user_exercice.jeu_de_test and user_exercice.jeu_de_test.reponse else ""
                        jeu_test_instance: str = "N/A"
                        if user_exercice.jeu_de_test:
                            jeu_test_instance = user_exercice.jeu_de_test.instance
                        zip_file.writestr(f"{user_folder}/reponse_{exercice_id}_{nom_participant}.txt",
                                          f"##### reponse_equipe :\n{solution}\n\n"
                                          f"##### reponse_attendue :\n{expected}\n\n"
                                          f"##### jeu_de_test :\n{jeu_test_instance}")

                    code = user_exercice.code_participant if user_exercice.code_participant else ""
                    zip_file.writestr(f"{user_folder}/code_{exercice_id}_{nom_participant}.py", code)
        elif by == 'participant':
            for user in User.objects.filter(user_exercices__exercice__epreuve=epreuve).distinct():
                nom_participant: str = user.username
                for user_exercice in user_exercices.filter(participant=user):
                    exercice: Exercice = user_exercice.exercice
                    exercice_folder = f"{nom_participant}/{exercice.titre}"
                    if exercice.avec_jeu_de_test:
                        solution = user_exercice.solution_instance_participant.strip() if user_exercice.solution_instance_participant else ""
                        expected = user_exercice.jeu_de_test.reponse.strip() if user_exercice.jeu_de_test and user_exercice.jeu_de_test.reponse else ""
                        jeu_test_instance: str = "N/A"
                        if user_exercice.jeu_de_test:
                            jeu_test_instance = user_exercice.jeu_de_test.instance
                        zip_file.writestr(f"{exercice_folder}/reponse_{nom_participant}_{exercice.id}.txt",
                                          f"##### reponse_equipe :\n{solution}\n\n"
                                          f"##### reponse_attendue :\n{expected}\n\n"
                                          f"##### jeu_de_test :\n{jeu_test_instance}")

                    code = user_exercice.code_participant if user_exercice.code_participant else ""
                    zip_file.writestr(f"{exercice_folder}/code_{nom_participant}_{exercice.id}.py", code)

    # Réinitialiser le curseur du fichier en mémoire
    zip_buffer.seek(0)

    # Créer la réponse HTTP avec le fichier zip en pièce jointe
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename={epreuve.nom[:30]}_{by}_data_export_{epreuve_id}.zip'
    return response


@login_required
@decorators.membre_comite_required
@transaction.atomic
def copier_epreuve(request: HttpRequest, epreuve_id: int):
    epreuve_originale: Epreuve = get_object_or_404(Epreuve, id=epreuve_id)
    """
    Vue pour copier une épreuve.
    L'épreuve créée est identique à l'épreuve dont l'id est en paramètre, 
    sauf le référent qui est l'utilisateur à l'origine de la copie, et le nom
    qui commence par "copie de".
    Les exercices associés à l'épreuve sont également copiés.
    Les jeux de données associés aux exercices sont également copiés, dans la limite
     de 5 par exercice.  
    
    Args:
        request (HttpRequest): L'objet requête HTTP.
        epreuve_id (int): L'identifiant de l'épreuve à copier

    Returns:
        HttpResponse: La réponse HTTP rendue.
    """

    # Création de la copie
    nouvelle_epreuve: Epreuve = Epreuve(
        nom=f"copie de {epreuve_originale.nom}",
        date_debut=epreuve_originale.date_debut,
        date_fin=epreuve_originale.date_fin,
        duree=epreuve_originale.duree,
        referent=epreuve_originale.referent,
        exercices_un_par_un=epreuve_originale.exercices_un_par_un,
        temps_limite=epreuve_originale.temps_limite,
        inscription_externe=False,  # forcé à False
    )
    nouvelle_epreuve.save()  # génère l'ID et le code automatiquement via save()

    # Ajout de request.user au comité de la nouvelle épreuve
    MembreComite.objects.create(epreuve=nouvelle_epreuve, membre=request.user)
    cinq_jeux_de_test: Optional[QuerySet[JeuDeTest]] = None
    for exercice in epreuve_originale.get_exercices():
        if exercice.avec_jeu_de_test:
            cinq_jeux_de_test = exercice.get_jeux_de_test()[:5]
        exercice.pk = None  # on crée un nouvel objet
        exercice.epreuve = nouvelle_epreuve
        exercice.auteur = request.user
        exercice.save()

        # Copie jusqu’à 5 jeux de tests, s’il y en a
        if exercice.avec_jeu_de_test:
            for jeu in cinq_jeux_de_test:
                # Création d’un nouveau jeu de test lié à l’exercice copié
                JeuDeTest.objects.create(
                    exercice=exercice,  # le nouvel exercice
                    instance=jeu.instance,
                    reponse=jeu.reponse
                )

    messages.success(request, f"L'épreuve a été copiée avec succès.")
    return redirect('espace_organisateur')


@login_required
@decorators.membre_comite_required
def exporter_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    """
    Exporte une épreuve au format JSON dans une archive ZIP contenant :
    - une version complète avec tous les jeux de test,
    - une version allégée avec seulement les 5 premiers jeux de test par exercice.

    Cette vue utilise une stratégie optimisée pour réduire les requêtes à la base de données,
    en préchargeant tous les exercices et leurs jeux de test associés.

    Args:
        request (HttpRequest): La requête HTTP envoyée par l'utilisateur.
        epreuve_id (int): Identifiant de l'épreuve à exporter.

    Returns:
        HttpResponse: Une réponse contenant une archive ZIP prête à être téléchargée.
    """

    # Récupération de l'épreuve ou 404 si elle n'existe pas
    epreuve: Epreuve = get_object_or_404(Epreuve, id=epreuve_id)

    # Préchargement de tous les exercices et jeux de test associés
    exercices_qs: List[Exercice] = (
        Epreuve.objects
        .prefetch_related(
            Prefetch("exercices", queryset=Exercice.objects.prefetch_related("jeudetest_set"))
        )
        .get(id=epreuve_id)
        .exercices.all()  # .exercices grâce au related_name
    )

    def construire_dictionnaire_export(max_tests: Optional[int] = None) -> Dict[str, Any]:
        """
        Construit un dictionnaire représentant l'épreuve et ses exercices,
        avec une option pour limiter le nombre de jeux de test.

        Args:
            max_tests (Optional[int]): Nombre maximal de jeux de test par exercice.
                Si None, inclut tous les jeux.

        Returns:
            Dict[str, Any]: Dictionnaire structuré pour export JSON.
        """
        dictionnaire_epreuve: Dict[str, Any] = {
            "nom": epreuve.nom,
            "date_debut": epreuve.date_debut.isoformat(),
            "date_fin": epreuve.date_fin.isoformat(),
            "duree": epreuve.duree,
            "exercices_un_par_un": epreuve.exercices_un_par_un,
            "temps_limite": epreuve.temps_limite,
            "exercices": []
        }

        for exercice in exercices_qs:
            dictionnaire_exercice: Dict[str, Any] = {
                "titre": exercice.titre,
                "auteur_username": exercice.auteur.username if exercice.auteur else None,
                "bareme": exercice.bareme,
                "type_exercice": exercice.type_exercice,
                "enonce": exercice.enonce,
                "enonce_code": exercice.enonce_code,
                "avec_jeu_de_test": exercice.avec_jeu_de_test,
                "separateur_jeu_test": exercice.separateur_jeu_test,
                "separateur_reponse_jeudetest": exercice.separateur_reponse_jeudetest,
                "retour_en_direct": exercice.retour_en_direct,
                "code_a_soumettre": exercice.code_a_soumettre,
                "nombre_max_soumissions": exercice.nombre_max_soumissions,
                "jeux_de_test": []
            }

            if exercice.avec_jeu_de_test:
                jeux_de_test: List[JeuDeTest] = list(exercice.jeudetest_set.all())
                if max_tests is not None:
                    jeux_de_test = jeux_de_test[:max_tests]
                dictionnaire_exercice["jeux_de_test"] = [
                    {"instance": jeu.instance, "reponse": jeu.reponse}
                    for jeu in jeux_de_test
                ]

            dictionnaire_epreuve["exercices"].append(dictionnaire_exercice)

        return dictionnaire_epreuve

    # Génération des deux versions JSON
    nom_slugifie: str = slugify(epreuve.nom)
    json_complet: str = json.dumps(construire_dictionnaire_export(), ensure_ascii=False, indent=2)
    json_light: str = json.dumps(construire_dictionnaire_export(max_tests=5), ensure_ascii=False, indent=2)

    # Création de l’archive ZIP en mémoire
    buffer_zip: io.BytesIO = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{nom_slugifie}_complete.json", json_complet)
        archive.writestr(f"{nom_slugifie}_light.json", json_light)

    # Préparation de la réponse HTTP
    buffer_zip.seek(0)
    response: HttpResponse = HttpResponse(buffer_zip, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="epreuve_{nom_slugifie}.zip"'
    return response
