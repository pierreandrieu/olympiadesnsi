from datetime import timedelta
from typing import List, Tuple, cast, Optional
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponseForbidden
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Count, Prefetch, QuerySet
from django.views.decorators.http import require_http_methods

from epreuve.forms import EpreuveForm
from epreuve.models import UserEpreuve, JeuDeTest, Epreuve, MembreComite, Exercice
from inscription.models import InscriptionOlympiades
from intranet.models import ParticipantEstDansGroupe, GroupeParticipant
from inscription.utils import save_users
from login.utils import genere_participants_uniques
from olympiadesnsi import decorators, settings
import olympiadesnsi.constants as constantes
from .classesdict import EpreuveDict, ExerciceDict, JeuDeTestDict
from django.conf import settings
import io
import json
import csv


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
    user: User = cast(User, request.user)

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

        referent: User = cast(User, request.user)

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
@decorators.administrateur_groupe_required
@require_http_methods(["POST"])
def telecharger_csv(request: HttpRequest) -> HttpResponse:
    groupe_id = request.POST.get('groupe_id')

    if groupe_id is None:
        return HttpResponseForbidden("Groupe non spécifié.")

    groupe = get_object_or_404(GroupeParticipant, id=groupe_id, referent=request.user)

    # On recrée un CSV minimal à partir des utilisateurs du groupe
    participants = groupe.participants()
    if not participants.exists():
        return redirect('espace_organisateur')

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Username'])

    for user in participants:
        writer.writerow([user.username])

    buffer.seek(0)
    nom_fichier = f'participants_{groupe.nom}.csv'
    response = HttpResponse(buffer.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'

    return response


@login_required
@decorators.organisateur_required
def afficher_page_telechargement(request: HttpRequest) -> HttpResponse:
    nom_groupe: str = request.session.get('nom_groupe')

    if not nom_groupe:
        return redirect('espace_organisateur')

    groupe: GroupeParticipant = get_object_or_404(GroupeParticipant, nom=nom_groupe, referent=request.user)

    return render(request, 'intranet/telecharge_csv_users.html', {
        'groupe': groupe
    })


@login_required
@decorators.organisateur_required
def creer_epreuve(request: HttpRequest) -> HttpResponse:
    """
    Vue responsable de la création d'une nouvelle épreuve.

    L'utilisateur doit être connecté et membre du groupe "Organisateur".
    """
    return _creer_ou_editer_epreuve(request)


@login_required
@decorators.administrateur_epreuve_required
def editer_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    """
    Vue d'édition d'une épreuve existante.

    L'utilisateur doit être membre du comité de l'épreuve pour accéder à cette page.

    Args:
        request: La requête HTTP.
        epreuve_id: Identifiant de l'épreuve à éditer.

    Returns:
        HttpResponse: Redirection ou affichage du formulaire d’édition.
    """
    epreuve = request.epreuve  # Injecté par le décorateur
    user = cast("User", request.user)

    if not epreuve.a_pour_membre_comite(user):
        return HttpResponseForbidden("Seuls les membres du comité d'organisation peuvent consulter cette page.")

    return _creer_ou_editer_epreuve(request, nouvelle=False, epreuve=epreuve)


def _creer_ou_editer_epreuve(
        request: HttpRequest,
        nouvelle: bool = True,
        epreuve: Optional[Epreuve] = None
) -> HttpResponse:
    """
    Gère la création ou la modification d'une épreuve via un formulaire unique.

    Si `epreuve` est fourni, on est en édition. Sinon, on est en création.

    - Remplit le formulaire
    - Valide et sauvegarde les données
    - Gère les domaines autorisés et le cache

    Args:
        request (HttpRequest): La requête HTTP entrante.
        nouvelle (bool): True pour une création, False pour une édition.
        epreuve (Optional[Epreuve]): L'épreuve à modifier, ou None pour une création.

    Returns:
        HttpResponse: La page HTML contenant le formulaire ou une redirection après succès.
    """
    domaines_autorises: str = ""
    if epreuve:
        domaines_autorises = epreuve.domaines_autorises_str()

    if request.method == 'POST':
        form: EpreuveForm = EpreuveForm(request.POST, instance=epreuve)

        if form.is_valid():
            epreuve = form.save(commit=False)
            if nouvelle:
                epreuve.referent = request.user
            epreuve.save()
            form.save_m2m()

            # Réordonne les exercices si un ordre est fourni
            exercice_ids_order = request.POST.getlist('exercice_order')
            epreuve.reordonner_exercices(exercice_ids_order)

            # Ajout au comité si nouvelle épreuve
            if nouvelle:
                epreuve.ajouter_au_comite(request.user)

            # Met à jour les domaines autorisés si nécessaire
            if epreuve.inscription_externe:
                domaines_str = form.cleaned_data.get('domaines_autorises', '')
                epreuve.mettre_a_jour_domaines(domaines_str)

            messages.success(
                request,
                f"L'épreuve {epreuve.nom} a été {'créée' if nouvelle else 'mise à jour'} avec succès."
            )
            return redirect('espace_organisateur')
    else:
        form = EpreuveForm(instance=epreuve, initial={'domaines_autorises': domaines_autorises})

    exercices = epreuve.exercices.order_by('numero') if epreuve else None
    return render(request, 'intranet/creer_epreuve.html', {
        'form': form,
        'epreuve': epreuve,
        'exercices': exercices,
    })


@login_required
@decorators.organisateur_required
@transaction.atomic
def importer_epreuve_json(request: HttpRequest) -> HttpResponse:
    """
    Permet à un organisateur d'importer une épreuve complète depuis un fichier JSON.
    Crée l'épreuve, les exercices et les jeux de test associés dans une transaction atomique.

    Args:
        request (HttpRequest): La requête HTTP POST avec un fichier JSON.

    Returns:
        HttpResponse: Page d'importation (GET) ou redirection vers l'espace organisateur (POST).
    """
    if request.method == "POST":
        json_file = request.FILES.get("json_file")
        if not json_file:
            messages.error(request, "Aucun fichier n’a été sélectionné.")
            return redirect('importer_epreuve_json')

        try:
            data: EpreuveDict = json.load(json_file)
        except json.JSONDecodeError:
            messages.error(request, "Le fichier n’est pas un JSON valide.")
            return redirect('importer_epreuve_json')

        # Création de l'épreuve
        nouvelle_epreuve: Epreuve = Epreuve.objects.create(
            nom=f"import de {data['nom']}",
            date_debut=data['date_debut'],
            date_fin=data['date_fin'],
            duree=data.get('duree'),
            referent=request.user,
            exercices_un_par_un=data.get('exercices_un_par_un', False),
            temps_limite=data.get('temps_limite', False),
            inscription_externe=False,
        )

        # Ajout du créateur comme membre du comité
        MembreComite.objects.create(epreuve=nouvelle_epreuve, membre=request.user)

        # Création des exercices
        exercices_importes: List[ExerciceDict] = data.get('exercices', [])
        for exo_data in exercices_importes:
            nouvel_exo: Exercice = Exercice.objects.create(
                epreuve=nouvelle_epreuve,
                auteur=request.user,
                titre=exo_data['titre'],
                bareme=exo_data.get('bareme'),
                type_exercice=exo_data.get('type_exercice', 'programmation'),
                enonce=exo_data.get('enonce'),
                enonce_code=exo_data.get('enonce_code'),
                avec_jeu_de_test=exo_data.get('avec_jeu_de_test', False),
                separateur_jeu_test=exo_data.get('separateur_jeu_test'),
                separateur_reponse_jeudetest=exo_data.get('separateur_reponse_jeudetest'),
                retour_en_direct=exo_data.get('retour_en_direct', False),
                code_a_soumettre=exo_data.get('code_a_soumettre', "python"),
                nombre_max_soumissions=exo_data.get('nombre_max_soumissions', 50)
            )

            if nouvel_exo.avec_jeu_de_test:
                jeux: List[JeuDeTestDict] = exo_data.get('jeux_de_test', [])
                for jeu in jeux:
                    JeuDeTest.objects.create(
                        exercice=nouvel_exo,
                        instance=jeu['instance'],
                        reponse=jeu['reponse']
                    )

        messages.success(request, f"L’épreuve « {nouvelle_epreuve.nom} » a été importée avec succès.")
        return redirect('espace_organisateur')

    return render(request, 'intranet/importer_epreuve_json.html')


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
    user: User = cast(User, request.user)

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
    epreuves_info: List[Tuple[Epreuve, int, list, int, int, int, List[User]]] = []
    for epreuve in epreuves_organisees:
        groupes_inscrits = list(epreuve.groupes_participants.all())
        nombre_exercices: int = epreuve.exercices.count()
        membres_comite: List[User] = list(User.objects.filter(membrecomite__epreuve=epreuve))
        nombre_organisateurs: int = len(membres_comite)
        epreuves_info.append((
            epreuve,
            nombre_organisateurs,
            groupes_inscrits,
            len(groupes_inscrits),
            epreuve.compte_participants_inscrits(),
            nombre_exercices,
            membres_comite
        ))

    epreuve_form: EpreuveForm = EpreuveForm()

    return render(request, 'intranet/espace_organisateur.html', {
        'nom': user.username,
        'groupes_crees': groupes_crees,
        'epreuves_info': epreuves_info,
        'form': epreuve_form,
        'olympiades_epreuve_id': int(getattr(django_settings, "OLYMPIADES_EPREUVE_ID", 0) or 0),
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
    email_contact = groupe.email_contact

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
        from django.core.mail import EmailMessage

        email = EmailMessage(
            subject=f"Liste des comptes pour l’épreuve {nom_epreuve}",
            body=(
                f"Bonjour,\n\n"
                f"Veuillez trouver en pièce jointe la liste des comptes associés à l’épreuve « {nom_epreuve} ».\n\n"
                f"Bien cordialement,\n"
                f"L'équipe des Olympiades de NSI"
            ),
            from_email=f"{settings.ADMIN_NAME} <{settings.EMAIL_HOST_USER}>",
            to=[email_contact],
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
@decorators.resolve_hashid_param("user_id")
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


@login_required
@decorators.organisateur_required
def exporter_inscriptions_olympiades_csv(request: HttpRequest) -> HttpResponse:
    id_olympiades: int = int(getattr(django_settings, "OLYMPIADES_EPREUVE_ID", 0) or 0)
    if id_olympiades == 0:
        return HttpResponseForbidden("Export indisponible : OLYMPIADES_EPREUVE_ID non configuré.")

    epreuve = Epreuve.objects.filter(id=id_olympiades).first()
    if epreuve is None or not epreuve.a_pour_membre_comite(request.user):
        return HttpResponseForbidden("Accès interdit.")

    inscriptions = (
        InscriptionOlympiades.objects
        .filter(epreuve=epreuve)
        .select_related("etablissement")
        .order_by("code_uai", "email_enseignant")
    )

    tampon = io.StringIO()
    writer = csv.writer(tampon, delimiter=";")
    writer.writerow([
        "nom_etablissement",
        "commune_etablissement",
        "uai",
        "mail_etablissement",
        "nom_enseignant",
        "mail_enseignant",
        "nb_candidats_ecrit",
        "nb_equipes_pratique",
    ])

    for ins in inscriptions:
        etab = ins.etablissement
        writer.writerow([
            etab.nom,
            etab.commune,
            ins.code_uai,
            etab.email,
            ins.nom_enseignant,
            ins.email_enseignant,
            int(ins.nb_candidats_ecrit),
            int(ins.nb_equipes_pratique),
        ])
    date_str = timezone.now().strftime("%Y%m%d-%H%M%S")
    nom_fichier = f"inscriptions_olympiades_epreuve_{epreuve.id}_{date_str}.csv"

    response = HttpResponse(tampon.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
    return response
