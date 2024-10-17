from datetime import timedelta
from typing import List, Tuple, Optional, Set

from django.core.mail import EmailMessage
from django.db import transaction
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpRequest
from django.shortcuts import render
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Count, Prefetch, QuerySet
from epreuve.models import User, Epreuve, MembreComite, Exercice, UserEpreuve
from inscription.models import InscriptionDomaine, GroupeParticipant
from intranet.models import ParticipantEstDansGroupe
from inscription.utils import save_users
from epreuve.forms import EpreuveForm
from login.utils import genere_participants_uniques
from olympiadesnsi import decorators, settings
import olympiadesnsi.constants as constantes
import csv
from django.conf import settings
import io


@login_required
@decorators.participant_required
def espace_participant(request: HttpRequest) -> HttpResponse:
    """
    Affiche l'espace participant, montrant les épreuves à venir, en cours, et terminées
    auxquelles l'utilisateur est inscrit.

    Args:
        request (HttpRequest): La requête HTTP envoyée par l'utilisateur.

    Returns:
        HttpResponse: La réponse HTTP rendue avec le template 'espace_participant.html',
                      contenant les informations des épreuves.
    """
    today: timezone.datetime = timezone.now()
    user: User = request.user

    epreuves_ids: QuerySet[int] = UserEpreuve.objects.filter(participant=user).values_list('epreuve_id', flat=True)
    # Récupération des associations UserEpreuve pour l'utilisateur
    user_epreuves: QuerySet[UserEpreuve] = (UserEpreuve.objects.filter
                                            (participant=user, epreuve_id__in=epreuves_ids).select_related('epreuve'))

    # Initialise les listes pour classer les épreuves
    epreuves_a_venir: List[Epreuve] = []
    epreuves_en_cours: List[Epreuve] = []
    epreuves_terminees: List[Epreuve] = []

    # Itère sur chaque association UserEpreuve pour l'utilisateur
    for user_epreuve in user_epreuves:
        epreuve: Epreuve = user_epreuve.epreuve  # Récupère l'épreuve associée à partir de l'association

        # Détermine si une fin d'épreuve spécifique à l'utilisateur est définie et si elle est passée
        fin_epreuve_specifique = (user_epreuve.debut_epreuve
                                  and epreuve.temps_limite
                                  and user_epreuve.debut_epreuve + timedelta(minutes=epreuve.duree) < today)

        if today < epreuve.date_debut:
            epreuves_a_venir.append(epreuve)
        elif epreuve.date_fin < today or fin_epreuve_specifique:
            epreuves_terminees.append(epreuve)
        else:
            epreuves_en_cours.append(epreuve)

    return render(request, 'intranet/espace_participant.html', {
        'epreuves_en_cours': epreuves_en_cours,
        'epreuves_a_venir': epreuves_a_venir,
        'epreuves_terminees': epreuves_terminees,
    })


@login_required
@decorators.participant_required
def gestion_compte_participant(request: HttpRequest) -> HttpResponse:
    return render(request, 'intranet/gestion_compte_participant.html')


@login_required
@decorators.organisateur_required
def gestion_compte_organisateur(request: HttpRequest) -> HttpResponse:
    return render(request, 'intranet/gestion_compte_organisateur.html')


@login_required
@decorators.organisateur_required
def creer_groupe(request: HttpRequest) -> HttpResponse:
    """
    Vue pour créer un nouveau groupe de participants.

    Args:
        request (HttpRequest): L'objet requête HTTP.

    Returns:
        HttpResponse: La réponse HTTP.
    """
    if request.method == 'POST':
        # Récupération et validation du nom du groupe
        nom_groupe: str = request.POST.get('nom_groupe').strip()
        if not nom_groupe:
            messages.error(request, "Le nom du groupe ne peut pas être vide.")
            return redirect('creer_groupe')

        # Validation du nombre de participants
        entree_utilisateur_nb_users: str = request.POST.get('nombre_utilisateurs').strip()
        if not entree_utilisateur_nb_users.isdigit():
            messages.error(request, "Le champ 'nombre de participants' doit être entier")
            return redirect('creer_groupe')

        nombre_utilisateurs: int = int(entree_utilisateur_nb_users)
        if not 0 < nombre_utilisateurs <= constantes.MAX_USERS_PAR_GROUPE:
            messages.error(request, f'Le nombre de participants doit être entre 1 et '
                                    f'{constantes.MAX_USERS_PAR_GROUPE}.')
            return redirect('creer_groupe')

        referent: User = request.user

        # Création ou récupération du groupe
        nouveau_groupe, created = GroupeParticipant.objects.get_or_create(
            nom=nom_groupe, referent=referent
        )

        if not created:
            messages.error(request, f'Vous avez déjà un groupe nommé {nom_groupe}.')
            return redirect('creer_groupe')

        # Génération des utilisateurs uniques
        users_info: List[str] = genere_participants_uniques(referent, nombre_utilisateurs)

        # Envoi des utilisateurs à créer en tâche de fond
        save_users(nouveau_groupe.id, users_info)
        # Préparation du fichier CSV pour téléchargement
        user_data = ["Utilisateurs"] + [f"{username}" for username in users_info]
        request.session['csv_data'] = "\n".join(user_data)
        request.session['nom_groupe'] = nom_groupe

        return redirect('afficher_page_telechargement')

    # Affichage du formulaire si pas POST ou en cas d'erreur
    return render(request, 'intranet/creer_groupe.html')


@login_required
@decorators.administrateur_groupe_required
def supprimer_groupe(request: HttpRequest, groupe_id: int) -> HttpResponse:
    """
    Supprime un groupe spécifié par son ID et les utilisateurs uniquement liés à ce groupe.

    Args:
        request (HttpRequest): La requête HTTP.
        groupe_id (int): L'ID du groupe à supprimer.

    Returns:
        HttpResponse: Redirection vers l'espace organisateur après traitement.
    """
    # Récupère le groupe spécifié par l'ID.

    if request.method == "POST":
        # L'objet groupe est récupéré par le décorateur administrateur_groupe_required
        groupe: GroupeParticipant = getattr(request, 'groupe', None)

        with transaction.atomic():
            # Récupère tous les participants du groupe.
            membres_du_groupe = [appartenance.utilisateur for appartenance in groupe.membres.all()]

            for participant in membres_du_groupe:
                # Vérifie si le participant appartient à d'autres groupes.
                if ParticipantEstDansGroupe.objects.filter(utilisateur=participant).count() == 1:
                    # Si le participant n'appartient à aucun autre groupe, le supprimer.
                    participant.delete()

            # Supprime le groupe.
            groupe.delete()
            messages.success(request, "Groupe supprimé avec succès.")
        return redirect('espace_organisateur')

    messages.error(request, "Méthode non supportée pour cette action.")
    return redirect('espace_organisateur')


@login_required
@decorators.organisateur_required
def telecharger_csv(request: HttpRequest) -> HttpResponse:
    """
    Permet à un organisateur de télécharger un fichier CSV contenant les noms d'utilisateur
    et mots de passe des participants récemment créés, à condition que l'organisateur soit
    bien l'administrateur du groupe concerné.

    Args:
        request (HttpRequest): La requête HTTP.

    Returns:
        HttpResponse: Une réponse HTTP qui soit initie le téléchargement du fichier CSV
        après vérification des droits de l'utilisateur, soit redirige vers l'espace organisateur,
        soit renvoie une réponse interdite si l'utilisateur n'est pas administrateur du groupe.
    """
    # Récupère le nom du groupe de la session.
    nom_groupe: str = request.session.get('nom_groupe', 'groupe_inconnu')

    # Tente de récupérer le groupe pour vérifier si l'utilisateur est bien l'administrateur.
    try:
        GroupeParticipant.objects.get(nom=nom_groupe, referent=request.user)
    except GroupeParticipant.DoesNotExist:
        # Si le groupe n'existe pas ou si l'utilisateur n'en est pas l'administrateur, interdit l'accès.
        return HttpResponseForbidden("Vous n'avez pas les droits nécessaires pour télécharger ce fichier.")

    # Procède au téléchargement si les vérifications sont passées.
    csv_data: str = request.session.get('csv_data')
    if csv_data is None:
        return redirect('espace_organisateur')

    nom_fichier: str = f"utilisateurs_{nom_groupe}.csv"
    response: HttpResponse = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'

    # Nettoie les données CSV de la session après leur utilisation.
    del request.session['csv_data']
    del request.session['nom_groupe']

    return response


@login_required
@decorators.organisateur_required
def afficher_page_telechargement(request: HttpRequest) -> HttpResponse:
    return render(request, 'intranet/telecharge_csv_users.html')


@login_required
@decorators.organisateur_required
def creer_editer_epreuve(request: HttpRequest, epreuve_id: Optional[int] = None) -> HttpResponse:
    """
    Crée ou édite une épreuve. Si un `epreuve_id` est fourni, l'épreuve correspondante est éditée.
    Sinon, une nouvelle épreuve est créée.

    Args:
        request (HttpRequest): La requête HTTP.
        epreuve_id (Optional[int]): L'identifiant de l'épreuve à éditer, si aucun, crée une nouvelle épreuve.

    Returns:
        HttpResponse: La réponse HTTP avec le formulaire de création/édition d'une épreuve.
    """
    domaines_autorises: str = ""
    epreuve: Optional[Epreuve] = None

    # si l'épreuve existe déjà, on est en mode édition
    if epreuve_id:
        epreuve = get_object_or_404(Epreuve, id=epreuve_id)
        if not epreuve.a_pour_membre_comite(request.user):
            return HttpResponseForbidden("Seuls les membres du comité d'organisation d'une épreuve sont "
                                         "peuvent consulter cette page.")

        # Récupère les domaines autorisés associés à l'épreuve pour pré-remplir le formulaire.
        domaines_qs: QuerySet[InscriptionDomaine] = InscriptionDomaine.objects.filter(epreuve=epreuve)
        domaines_autorises: str = "\n".join([domaine.domaine for domaine in domaines_qs])

    if request.method == 'POST':
        form: EpreuveForm = EpreuveForm(request.POST, instance=epreuve)
        if form.is_valid():
            epreuve: Epreuve = form.save(commit=False)
            epreuve.referent = request.user
            epreuve.save()
            form.save_m2m()  # Sauvegarde les relations many-to-many spécifiées dans le formulaire.

            # Met à jour l'ordre des exercices si fourni.
            exercice_ids_order = request.POST.getlist('exercice_order')
            for index, exercice_id in enumerate(exercice_ids_order, start=1):
                Exercice.objects.filter(id=exercice_id).update(numero=index)

            # Ajoute l'utilisateur actuel comme membre du comité de l'épreuve si c'est une création.
            if epreuve_id is None:
                MembreComite.objects.create(epreuve=epreuve, membre=request.user)

            # Gère l'ajout/suppression des domaines autorisés pour les inscriptions externes.
            if epreuve.inscription_externe:
                InscriptionDomaine.objects.filter(epreuve=epreuve).delete()
                domaines_str: str = form.cleaned_data['domaines_autorises']
                domaines_set: Set[str] = {d.strip() for d in domaines_str.split('\n') if d.strip().startswith('@')}
                for domaine in domaines_set:
                    InscriptionDomaine.objects.create(epreuve=epreuve, domaine=domaine)

            action: str = 'créée' if not epreuve_id else 'mise à jour'
            messages.success(request, f"L'épreuve {epreuve.nom} a été {action} avec succès.")
            return redirect('espace_organisateur')
    else:
        form: EpreuveForm = EpreuveForm(instance=epreuve, initial={'domaines_autorises': domaines_autorises})

    return render(request, 'intranet/creer_epreuve.html', {
        'form': form,
        'epreuve': epreuve,
    })


@login_required
@decorators.organisateur_required
def espace_organisateur(request: HttpRequest) -> HttpResponse:
    """
    Affiche l'espace de l'organisateur avec la liste des groupes créés par l'utilisateur
    et les épreuves qu'il organise.

    Args:
        request (HttpRequest): La requête HTTP.

    Returns:
        HttpResponse: La réponse HTTP rendue avec le template de l'espace organisateur.
    """
    user: User = request.user

    # Récupération des groupes créés par l'utilisateur avec le nombre de membres associés à chaque groupe.
    groupes_crees: QuerySet[GroupeParticipant] = GroupeParticipant.objects.filter(referent=user) \
        .annotate(nombre_membres=Count('membres'))

    # Préparation des requêtes pré-fetch pour optimiser les accès aux données des épreuves.
    exercice_prefetch: Prefetch = Prefetch('exercices', queryset=Exercice.objects.order_by('numero'))
    epreuves_organisees: QuerySet[Epreuve] = Epreuve.objects.filter(
        membrecomite__membre=user
    ).prefetch_related(
        exercice_prefetch,
        'groupes_participants',
        Prefetch('membrecomite_set', queryset=MembreComite.objects.select_related('membre'))
    )

    # Compilation des informations à afficher pour chaque épreuve organisée.
    epreuves_info: List[Tuple[Epreuve, int, QuerySet, int, int, int, List[User]]] = []
    for epreuve in epreuves_organisees:
        nombre_groupes: int = epreuve.groupes_participants.count()

        groupes_participants_ids = epreuve.groupes_participants.values_list('id', flat=True)

        # Utilisez ParticipantEstDansGroupe pour trouver tous les utilisateurs (participants)
        # qui sont dans ces groupes.
        participants_uniques_count = ParticipantEstDansGroupe.objects.filter(
            groupe_id__in=groupes_participants_ids
        ).distinct('utilisateur').count()

        nombre_exercices: int = epreuve.exercices.count()
        membres_comite: List[User] = list(User.objects.filter(membrecomite__epreuve=epreuve))
        nombre_organisateurs: int = len(membres_comite)
        epreuves_info.append((epreuve, nombre_organisateurs, epreuve.groupes_participants.all(), nombre_groupes,
                              participants_uniques_count, nombre_exercices, membres_comite))

    epreuve_form: EpreuveForm = EpreuveForm()

    return render(request, 'intranet/espace_organisateur.html', {
        'nom': user.username,
        'groupes_crees': groupes_crees,
        'epreuves_info': epreuves_info,
        'form': epreuve_form
    })


@login_required
def change_password_generic(request, template, vue):
    form = PasswordChangeForm(request.user, request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.save()

        #  Maintenir la session de l'utilisateur
        update_session_auth_hash(request, user)
        messages.success(request, 'Votre mot de passe a été mis à jour avec succès!')
        return redirect(
            vue)  # Rediriger vers une URL spécifique après la mise à jour réussie

    return render(request, template, {'form': form})


@login_required
@decorators.participant_required
def change_password_participant(request):
    return change_password_generic(request, "intranet/change_password_participant.html",
                                   "espace_participant")


@login_required
@decorators.organisateur_required
def change_password_organisateur(request):
    return change_password_generic(request, "intranet/change_password_organisateur.html",
                                   "espace_organisateur")


@login_required
@decorators.administrateur_groupe_required
def envoyer_email_participants(request: HttpRequest, groupe_id: int) -> HttpResponse:
    groupe: GroupeParticipant = getattr(request, 'groupe', None)

    email_contact = groupe.email_contact()

    if email_contact:
        output = io.StringIO()
        writer = csv.writer(output)

        # Entête du fichier CSV
        writer.writerow(['username'])

        # Écrire chaque participant dans le CSV
        for participant in groupe.membres.all():
            writer.writerow([participant.utilisateur.username])

        # S'assurer que le pointeur est bien au début du fichier
        output.seek(0)
        nom_epreuve: str = groupe.inscription_externe.epreuve.nom
        email = EmailMessage(
            "Liste des comptes pour l'épreuve " + nom_epreuve,
            "Vous trouverez en pièce jointe la liste de vos comptes inscrits à l'épreuve " + nom_epreuve + ".",
            settings.EMAIL_HOST_USER,
            [email_contact]
        )

        # Attacher le fichier CSV
        email.attach('liste_participants.csv', output.getvalue(), 'text/csv')

        # Envoyer l'email
        email.send()

        messages.success(request, "L'email a été envoyé avec succès à {}.".format(email_contact))
    else:
        messages.error(request, "Aucun email de contact trouvé pour ce groupe.")

    return redirect('espace_organisateur')


@login_required
@decorators.organisateur_required
def reset_password(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.is_active = False
        user.set_unusable_password()  # Rend le mot de passe actuel inutilisable
        user.save()
        messages.success(request, 'Le compte utilisateur est prêt pour une réinitialisation de mot de passe.')
    except User.DoesNotExist:
        messages.error(request, 'Utilisateur non trouvé.')
    return redirect('espace_organisateur')