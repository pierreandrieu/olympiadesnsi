from __future__ import annotations

import csv
import io
import zipfile
from typing import Iterable, List, Optional

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from epreuve.models import Epreuve
from inscription.forms import (
    DemandeLienOlympiadesForm,
    EditionInscriptionOlympiadesForm,
    InscriptionOlympiadesForm, InscriptionAnnalesForm,
)
from inscription.models import (
    Etablissement,
    InscripteurExterne,
    InscriptionDomaine,
    InscriptionExterne,
    InscriptionOlympiades,
    InscriptionOlympiadesGroupe,
    GroupeParticipeAEpreuve, InscriptionAnnales, AnonymatEpreuveEcrite,
)
from inscription.services.olympiades import (
    inscrire_groupe_olympiades_a_epreuve,
    preparer_groupe_et_comptes_olympiades, preparer_groupe_et_comptes_annales, ajuster_anonymats_epreuve_ecrite,
    generer_csv_epreuve_ecrite_depuis_inscription, lister_comptes_resetables, inscriptions_ouvertes,
)
from inscription.utils import generate_unique_token
from intranet.models import GroupeParticipant
from olympiadesnsi import settings


# ---------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------

def _get_epreuve_olympiades() -> Optional[Epreuve]:
    """
    Retourne l'épreuve "Olympiades" courante configurée par `settings.OLYMPIADES_EPREUVE_ID`.

    Returns:
        Optional[Epreuve]: L'épreuve courante si elle existe, sinon None.
    """
    epreuve_id: int = int(getattr(settings, "OLYMPIADES_EPREUVE_ID", 0))
    if epreuve_id == 0:
        return None
    return Epreuve.objects.filter(id=epreuve_id).first()


def _groupes_de_l_inscription(inscription: InscriptionOlympiades) -> Iterable[GroupeParticipant]:
    """
    Retourne tous les groupes (GroupeParticipant) rattachés à l'inscription,
    tous types confondus.

    Args:
        inscription: Inscription olympiades.

    Yields:
        GroupeParticipant: Groupes rattachés via InscriptionOlympiadesGroupe.
    """
    liens = (
        inscription.groupes_associes
        .select_related("groupe")
        .all()
    )
    for lien in liens:
        yield lien.groupe


def _supprimer_inscription_olympiades_et_dependances(inscription: InscriptionOlympiades) -> None:
    """
    Supprime une inscription olympiades et ses dépendances :

    - Désinscription des groupes des épreuves concernées
      (via Epreuve.desinscrire_groupe -> nettoie UserEpreuve/UserExercice/etc.)
    - Suppression des liens InscriptionOlympiadesGroupe
    - Suppression des groupes dédiés (si non utilisés ailleurs)
    - Suppression de l'objet InscriptionOlympiades

    Important :
        - Ne touche pas au référentiel Etablissement.
        - Gère le cas où un groupe serait réutilisé par une autre inscription (garde-fou).

    Args:
        inscription: Inscription à supprimer.
    """
    epreuve: Epreuve = inscription.epreuve

    groupes: List[GroupeParticipant] = list(_groupes_de_l_inscription(inscription))

    # 1) Désinscrire proprement des épreuves
    for groupe in groupes:
        est_utilise_par_une_autre_inscription: bool = (
            InscriptionOlympiadesGroupe.objects
            .filter(groupe=groupe)
            .exclude(inscription=inscription)
            .exists()
        )

        if GroupeParticipeAEpreuve.objects.filter(epreuve=epreuve, groupe=groupe).exists():
            epreuve.desinscrire_groupe(groupe)

        # Si le groupe est partagé, on ne le supprime pas.
        if est_utilise_par_une_autre_inscription:
            continue

    # 2) Supprimer les liens inscription<->groupe
    inscription.groupes_associes.all().delete()

    # 3) Supprimer les groupes dédiés (non partagés)
    for groupe in groupes:
        est_utilise_par_une_autre_inscription = (
            InscriptionOlympiadesGroupe.objects
            .filter(groupe=groupe)
            .exclude(inscription=inscription)
            .exists()
        )
        if not est_utilise_par_une_autre_inscription:
            groupe.delete()

    AnonymatEpreuveEcrite.objects.filter(inscription=inscription, actif=True).update(actif=False)
    # 4) Supprimer l'inscription
    inscription.delete()


# ---------------------------------------------------------------------
# Vues : demande de lien / inscription
# ---------------------------------------------------------------------

@ratelimit(key="ip", rate="3/s", method="GET", block=True)
@ratelimit(key="ip", rate="15/m", method="GET", block=True)
@ratelimit(key="ip", rate="50/h", method="GET", block=True)
def olympiades_demande_lien(request: HttpRequest) -> HttpResponse:
    """
    Page "Demander un lien d'inscription".

    L'enseignant saisit son identifiant académique + choisit un domaine autorisé.
    On crée ensuite une InscriptionExterne avec un token unique et on envoie un email
    contenant l'URL du portail tokenisé.

    Args:
        request: Requête HTTP.

    Returns:
        HttpResponse: Formulaire (GET / POST invalide) ou confirmation (POST valide).
    """
    epreuve: Optional[Epreuve] = _get_epreuve_olympiades()
    if epreuve is None:
        return render(request, "inscription/olympiades_fermees.html")

    domaines: List[str] = list(
        InscriptionDomaine.objects.filter(epreuve=epreuve)
        .order_by("domaine")
        .values_list("domaine", flat=True)
    )

    form: DemandeLienOlympiadesForm = DemandeLienOlympiadesForm(
        request.POST or None,
        domaines=domaines,
    )

    if request.method == "POST" and form.is_valid():
        identifiant: str = str(form.cleaned_data["identifiant"])
        domaine: str = str(form.cleaned_data["domaine_academique"])

        if not domaine:
            messages.error(request, "Il faut sélectionner un domaine académique.")
            return render(request, "inscription/olympiades_demande_lien.html", {"form": form, "epreuve": epreuve})

        email_enseignant: str = f"{identifiant}{domaine}"

        inscripteur, _ = InscripteurExterne.objects.get_or_create(email=email_enseignant)

        token: str = generate_unique_token()
        inscription_externe: InscriptionExterne = InscriptionExterne.objects.create(
            inscripteur=inscripteur,
            token=token,
            epreuve=epreuve,
            date_creation=timezone.now(),
            token_est_utilise=False,
        )

        lien: str = request.build_absolute_uri(reverse("olympiades_portail", args=[inscription_externe.token]))

        sujet: str = f"Olympiades NSI – lien d'inscription ({epreuve.nom})"
        corps: str = (
            "Bonjour,\n\n"
            "Vous avez demandé un lien d'inscription pour les Olympiades NSI.\n\n"
            f"Lien : {lien}\n\n"
            "Ce lien est valable pendant 24 heures.\n\n"
            "Cordialement,\n"
            "L’équipe des Olympiades de NSI"
        )

        mail: EmailMessage = EmailMessage(
            subject=sujet,
            body=corps,
            from_email=f"{settings.ADMIN_NAME} <{settings.EMAIL_HOST_USER}>",
            to=[email_enseignant],
        )
        mail.send()

        return render(request, "inscription/olympiades_confirmation_envoi_lien.html", {"email": email_enseignant})

    return render(request, "inscription/olympiades_demande_lien.html", {"form": form, "epreuve": epreuve})

# ---------------------------------------------------------------------
# Portail
# ---------------------------------------------------------------------


def olympiades_portail(request: HttpRequest, token: str) -> HttpResponse:
    """
    Portail enseignant : affiche les inscriptions olympiades et annales
    associées à l'email du token.

    - Olympiades : inscriptions par établissement
    - Annales : générations de comptes plateforme (sans épreuve papier)

    Args:
        request: Requête HTTP.
        token: Token d'accès enseignant.

    Returns:
        HttpResponse: Page HTML du portail.
    """
    inscription_externe: InscriptionExterne = get_object_or_404(
        InscriptionExterne,
        token=token,
        token_est_utilise=False,
    )
    ouvert = inscriptions_ouvertes()
    if not inscription_externe.est_valide:
        return render(request, "inscription/erreur_lien_expire.html")

    epreuve: Epreuve = inscription_externe.epreuve
    email_enseignant: str = inscription_externe.inscripteur.email

    # ------------------------------------------------------------------
    # Inscriptions olympiades (par établissement)
    # ------------------------------------------------------------------
    inscriptions = (
        InscriptionOlympiades.objects
        .filter(epreuve=epreuve, email_enseignant=email_enseignant)
        .select_related("etablissement")
        .prefetch_related("groupes_associes__groupe")
        .order_by("etablissement__nom")
    )

    for inscription in inscriptions:
        groupes_pratique = [
            lien
            for lien in inscription.groupes_associes.all()
            if lien.type_groupe == InscriptionOlympiadesGroupe.TYPE_OLYMPIADES
        ]
        inscription.groupes_pratique = groupes_pratique
        inscription.nb_equipes_pratique_total = sum(
            lien.groupe.get_nombre_participants()
            for lien in groupes_pratique
        )

    # ------------------------------------------------------------------
    # Annales (plateforme uniquement, sans papier)
    # ------------------------------------------------------------------
    annales: List[Epreuve] = list(epreuve.lister_annales())

    inscriptions_annales = (
        InscriptionAnnales.objects
        .filter(epreuve=epreuve, email_enseignant=email_enseignant)  # epreuve = épreuve source du token
        .select_related("epreuve")
        .prefetch_related("groupes_associes")
        .order_by("-date_maj")
    )

    for inscription_annales in inscriptions_annales:
        inscription_annales.nb_equipes_total = sum(
            groupe.get_nombre_participants()
            for groupe in inscription_annales.groupes_associes.all()
        )
        inscription_annales.nb_lots = inscription_annales.groupes_associes.count()

    return render(
        request,
        "inscription/olympiades_portail.html",
        {
            "epreuve": epreuve,
            "email_enseignant": email_enseignant,
            "inscriptions": inscriptions,
            "inscriptions_annales": inscriptions_annales,
            "token": token,
            "annales": annales,
            "inscriptions_ouvertes": ouvert,
        },
    )


# ---------------------------------------------------------------------
# Téléchargement ZIP
# ---------------------------------------------------------------------

def telecharger_zip_inscription(request: HttpRequest, token: str, inscription_id: int) -> HttpResponse:
    """
    Télécharge un zip contenant :
    - un CSV "papier" (identifiants candidats)
    - un CSV par groupe pratique (usernames)

    Sécurisé par le token : l'inscription doit appartenir à (épreuve, email_enseignant) du token.

    Args:
        request: Requête HTTP.
        token: Token enseignant.
        inscription_id: ID de l'inscription.

    Returns:
        HttpResponse: Fichier zip.
    """
    inscription_externe: InscriptionExterne = get_object_or_404(
        InscriptionExterne,
        token=token,
        token_est_utilise=False,
    )
    if not inscription_externe.est_valide:
        return render(request, "inscription/erreur_lien_expire.html")

    inscription: InscriptionOlympiades = get_object_or_404(
        InscriptionOlympiades,
        id=inscription_id,
        epreuve=inscription_externe.epreuve,
        email_enseignant=inscription_externe.inscripteur.email,
    )

    buffer: io.BytesIO = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        contenu_csv_papier = generer_csv_epreuve_ecrite_depuis_inscription(inscription=inscription)
        nom_csv_papier = f"{inscription.code_uai}_anonymat_epreuve_ecrite.csv"
        zf.writestr(nom_csv_papier, contenu_csv_papier)

        # CSV pratique : un fichier par groupe
        groupes = (
            inscription.groupes_associes.filter(type_groupe=InscriptionOlympiadesGroupe.TYPE_OLYMPIADES)
            .select_related("groupe")
            .order_by("numero")
        )

        for lien in groupes:
            contenu = io.StringIO()
            w = csv.writer(contenu, delimiter=";")
            w.writerow(["username"])
            for user in lien.groupe.participants():
                w.writerow([user.username])

            zf.writestr(
                f"{inscription.code_uai}_identifiants_pratique_{int(lien.numero):03d}.csv",
                contenu.getvalue(),
            )

    buffer.seek(0)
    nom_epreuve_fichier = inscription.epreuve.nom.replace(" ", "")[:20]
    nom_zip: str = f"inscription_{nom_epreuve_fichier}_{inscription.email_enseignant}.zip"

    reponse: HttpResponse = HttpResponse(buffer.getvalue(), content_type="application/zip")
    reponse["Content-Disposition"] = f'attachment; filename="{nom_zip}"'
    return reponse


# ---------------------------------------------------------------------
# Nouvelle inscription depuis portail
# ---------------------------------------------------------------------

def olympiades_nouvelle_inscription(request: HttpRequest, token: str) -> HttpResponse:
    """
    Ajoute un nouvel établissement depuis le portail enseignant.

    Particularité :
        - Ici, on BLOQUE si l'enseignant tente d'ajouter un établissement déjà enregistré par lui
          sur la même épreuve (au lieu de "mettre à jour").

    Args:
        request: Requête HTTP.
        token: Token d'accès.

    Returns:
        HttpResponse: Page du formulaire ou redirection vers le portail.
    """
    if not inscriptions_ouvertes():
        messages.error(request,
                       "La période d’inscription est terminée.")
        return redirect("olympiades_portail", token=token)
    inscription_externe: InscriptionExterne = get_object_or_404(
        InscriptionExterne,
        token=token,
        token_est_utilise=False,
    )
    if not inscription_externe.est_valide:
        return render(request, "inscription/erreur_lien_expire.html")

    epreuve: Epreuve = inscription_externe.epreuve
    email_enseignant: str = inscription_externe.inscripteur.email

    form: InscriptionOlympiadesForm = InscriptionOlympiadesForm(request.POST or None)

    if request.method != "POST" or not form.is_valid():
        return render(
            request,
            "inscription/olympiades_nouvelle_inscription.html",
            {"form": form, "epreuve": epreuve, "email_enseignant": email_enseignant, "token": token},
        )

    code_uai: str = (form.cleaned_data["code_uai"] or "").strip().upper()
    nom_etablissement: str = (form.cleaned_data.get("nom_etablissement") or "").strip()
    commune: str = (form.cleaned_data.get("commune") or "").strip()
    email_etablissement: str = (form.cleaned_data.get("email_etablissement") or "").strip()
    nom_enseignant: str = (form.cleaned_data.get("nom_enseignant") or "").strip()
    nb_candidats_ecrit: int = int(form.cleaned_data["nb_candidats_ecrit"])
    nb_equipes_pratique: int = int(form.cleaned_data["nb_equipes_pratique"])

    etablissement, _ = Etablissement.objects.update_or_create(
        code_uai=code_uai,
        defaults={"nom": nom_etablissement, "commune": commune, "email": email_etablissement},
    )

    deja_inscrit: bool = InscriptionOlympiades.objects.filter(
        epreuve=epreuve,
        etablissement=etablissement,
        email_enseignant=email_enseignant,
    ).exists()

    if deja_inscrit:
        form.add_error("code_uai", "Cet établissement est déjà inscrit pour cette épreuve avec cet email enseignant.")
        messages.error(request, "Établissement déjà inscrit : vous l’avez déjà enregistré avec cet email enseignant.")
        return render(
            request,
            "inscription/olympiades_nouvelle_inscription.html",
            {"form": form, "epreuve": epreuve, "email_enseignant": email_enseignant, "token": token},
        )

    try:
        with transaction.atomic():
            inscription: InscriptionOlympiades = InscriptionOlympiades.objects.create(
                epreuve=epreuve,
                etablissement=etablissement,
                code_uai=code_uai,
                email_enseignant=email_enseignant,
                nom_enseignant=nom_enseignant,
                nb_candidats_ecrit=nb_candidats_ecrit,
                nb_equipes_pratique=nb_equipes_pratique,
            )
            ajuster_anonymats_epreuve_ecrite(inscription=inscription, nb_voulu=nb_candidats_ecrit)
    except IntegrityError:
        form.add_error("code_uai", "Cet établissement est déjà inscrit pour cette épreuve avec cet email enseignant.")
        messages.error(request, "Établissement déjà inscrit : vous l’avez déjà enregistré avec cet email enseignant.")
        return render(
            request,
            "inscription/olympiades_nouvelle_inscription.html",
            {"form": form, "epreuve": epreuve, "email_enseignant": email_enseignant, "token": token},
        )

    if nb_equipes_pratique > 0:
        referent: User = epreuve.referent
        groupe_olympiades, _usernames = preparer_groupe_et_comptes_olympiades(
            epreuve=epreuve,
            referent=referent,
            code_uai=code_uai,
            email_enseignant=email_enseignant,
            nb_equipes=nb_equipes_pratique,
            inscription=inscription,
        )
        inscrire_groupe_olympiades_a_epreuve(epreuve=epreuve, groupe_olympiades=groupe_olympiades)

    messages.success(request, "Inscription enregistrée.")
    return redirect("olympiades_portail", token=token)


# ---------------------------------------------------------------------
# Édition : maj papier + ajout d'équipes pratique
# ---------------------------------------------------------------------

def olympiades_editer_inscription(request: HttpRequest, token: str, inscription_id: int) -> HttpResponse:
    """
    Édite une inscription olympiades depuis le portail enseignant.

    Champs modifiables :
        - nb_candidats_ecrit
        - ajout d'un nouveau groupe pratique (nb_equipes_a_ajouter)

    Important :
        - Pour la pratique, on ajoute un nouveau groupe numéroté (001, 002, ...) et on inscrit le groupe à l'épreuve.

    Args:
        request: Requête HTTP.
        token: Token enseignant.
        inscription_id: ID de l'inscription.

    Returns:
        HttpResponse: Page d'édition ou redirection après succès.
    """
    if not inscriptions_ouvertes():
        messages.error(request,
                       "La période d’inscription est terminée.")
        return redirect("olympiades_portail", token=token)
    inscription_externe: InscriptionExterne = get_object_or_404(
        InscriptionExterne,
        token=token,
        token_est_utilise=False,
    )
    if not inscription_externe.est_valide:
        return render(request, "inscription/erreur_lien_expire.html")

    epreuve: Epreuve = inscription_externe.epreuve
    email_enseignant: str = inscription_externe.inscripteur.email

    inscription: InscriptionOlympiades = get_object_or_404(
        InscriptionOlympiades,
        id=inscription_id,
        epreuve=epreuve,
        email_enseignant=email_enseignant,
    )

    groupes_pratique = (
        inscription.groupes_associes.filter(type_groupe=InscriptionOlympiadesGroupe.TYPE_OLYMPIADES)
        .select_related("groupe")
        .order_by("numero")
    )

    initial: dict[str, int] = {
        "nb_candidats_ecrit": int(inscription.nb_candidats_ecrit),
        "nb_equipes_a_ajouter": 0,
    }
    form: EditionInscriptionOlympiadesForm = EditionInscriptionOlympiadesForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        nb_candidats_ecrit: int = int(form.cleaned_data["nb_candidats_ecrit"])
        nb_equipes_a_ajouter: int = int(form.cleaned_data["nb_equipes_a_ajouter"])

        with transaction.atomic():
            inscription.nb_candidats_ecrit = nb_candidats_ecrit
            inscription.nb_equipes_pratique += nb_equipes_a_ajouter
            inscription.save(update_fields=["nb_candidats_ecrit", "nb_equipes_pratique", "date_maj"])
            ajuster_anonymats_epreuve_ecrite(inscription=inscription, nb_voulu=nb_candidats_ecrit)
            if nb_equipes_a_ajouter > 0:
                referent: User = epreuve.referent
                groupe_olympiades, _usernames = preparer_groupe_et_comptes_olympiades(
                    epreuve=epreuve,
                    referent=referent,
                    code_uai=inscription.code_uai,
                    email_enseignant=inscription.email_enseignant,
                    nb_equipes=nb_equipes_a_ajouter,
                    inscription=inscription,
                )
                # inscription réelle du groupe à l'épreuve
                inscrire_groupe_olympiades_a_epreuve(epreuve=epreuve, groupe_olympiades=groupe_olympiades)

        if nb_equipes_a_ajouter > 0:
            messages.success(
                request,
                f"Un ensemble de {nb_equipes_a_ajouter} équipes a été ajouté pour l'épreuve pratique.",
            )
        else:
            messages.success(request, "Modifications enregistrées.")

        return redirect("olympiades_editer_inscription", token=token, inscription_id=inscription.id)

    return render(
        request,
        "inscription/olympiades_editer_inscription.html",
        {
            "epreuve": epreuve,
            "email_enseignant": email_enseignant,
            "token": token,
            "inscription": inscription,
            "form": form,
            "groupes_pratique": groupes_pratique,
        },
    )


# ---------------------------------------------------------------------
# Préremplissage établissement
# ---------------------------------------------------------------------

@require_GET
def olympiades_infos_etablissement(request: HttpRequest) -> JsonResponse:
    """
    Endpoint JSON appelé par le JS de préremplissage lors de la saisie d'un UAI.

    Répond :
        - ok: bool
        - existe: bool (Etablissement trouvé ?)
        - deja_inscrit_par_ce_prof: bool (même epreuve et même email du token)
        - etablissement: {...} si existe=True

    Query params :
        - code_uai: str (obligatoire)
        - token: str (optionnel)

    Args:
        request: Requête HTTP.

    Returns:
        JsonResponse: Données établissement.
    """
    code_uai: str = (request.GET.get("code_uai") or "").strip().upper()
    token: str = (request.GET.get("token") or "").strip()

    if not code_uai:
        return JsonResponse({"ok": False, "error": "UAI manquant."}, status=400)

    deja_inscrit_par_ce_prof: bool = False
    etab: Optional[Etablissement] = Etablissement.objects.filter(code_uai=code_uai).first()

    if token:
        inscription_externe: Optional[InscriptionExterne] = InscriptionExterne.objects.filter(
            token=token,
            token_est_utilise=False,
        ).first()

        if inscription_externe is not None and inscription_externe.est_valide and etab is not None:
            deja_inscrit_par_ce_prof = InscriptionOlympiades.objects.filter(
                epreuve=inscription_externe.epreuve,
                etablissement=etab,
                email_enseignant=inscription_externe.inscripteur.email,
            ).exists()

    if etab is None:
        return JsonResponse({"ok": True, "existe": False, "deja_inscrit_par_ce_prof": deja_inscrit_par_ce_prof})

    return JsonResponse(
        {
            "ok": True,
            "existe": True,
            "deja_inscrit_par_ce_prof": deja_inscrit_par_ce_prof,
            "etablissement": {
                "code_uai": etab.code_uai,
                "nom_etablissement": etab.nom,
                "commune": etab.commune,
                "email_etablissement": etab.email,
            },
        }
    )


# ---------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------

def olympiades_supprimer_inscription(request: HttpRequest, token: str, inscription_id: int) -> HttpResponse:
    """
    Confirmation + suppression d'une inscription olympiades depuis le portail enseignant.

    Sécurité :
        - token valide
        - inscription appartenant à (epreuve, email_enseignant) du token

    Args:
        request: Requête HTTP.
        token: Token enseignant.
        inscription_id: ID de l'inscription.

    Returns:
        HttpResponse: Page de confirmation ou redirection après suppression.
    """
    if not inscriptions_ouvertes():
        messages.error(request,
                       "La période d’inscription est terminée.")
        return redirect("olympiades_portail", token=token)
    inscription_externe: InscriptionExterne = get_object_or_404(
        InscriptionExterne,
        token=token,
        token_est_utilise=False,
    )
    if not inscription_externe.est_valide:
        return render(request, "inscription/erreur_lien_expire.html")

    epreuve: Epreuve = inscription_externe.epreuve
    email_enseignant: str = inscription_externe.inscripteur.email

    inscription: InscriptionOlympiades = get_object_or_404(
        InscriptionOlympiades,
        id=inscription_id,
        epreuve=epreuve,
        email_enseignant=email_enseignant,
    )

    groupes_pratique = (
        inscription.groupes_associes
        .filter(type_groupe=InscriptionOlympiadesGroupe.TYPE_OLYMPIADES)
        .select_related("groupe")
        .order_by("numero")
    )
    nb_equipes_total: int = sum(lien.groupe.get_nombre_participants() for lien in groupes_pratique)

    if request.method == "POST":
        with transaction.atomic():
            _supprimer_inscription_olympiades_et_dependances(inscription)

        messages.success(request, "L’inscription a été supprimée (groupes et inscriptions associés inclus).")
        return redirect("olympiades_portail", token=token)

    return render(
        request,
        "inscription/olympiades_supprimer_inscription.html",
        {
            "token": token,
            "epreuve": epreuve,
            "email_enseignant": email_enseignant,
            "inscription": inscription,
            "groupes_pratique": groupes_pratique,
            "nb_equipes_total": nb_equipes_total,
        },
    )


def annales_inscrire(request: HttpRequest, token: str) -> HttpResponse:
    """
    Génère des comptes "équipes" utilisables sur toutes les annales liées à l'épreuve du token.

    Convention :
        - 1 génération = 1 groupe
        - le groupe est inscrit à toutes les annales renvoyées par epreuve_source.lister_annales()
        - le groupe est rattaché à InscriptionAnnales via le ManyToMany groupes_associes
        - l'URL ne contient pas annale_id (pas de garde-fou par annale)
    """
    inscription_externe: InscriptionExterne = get_object_or_404(
        InscriptionExterne,
        token=token,
        token_est_utilise=False,
    )
    if not inscription_externe.est_valide:
        return render(request, "inscription/erreur_lien_expire.html")

    epreuve_source: Epreuve = inscription_externe.epreuve
    email_enseignant: str = inscription_externe.inscripteur.email

    annales_cibles: List[Epreuve] = list(epreuve_source.lister_annales())
    if not annales_cibles:
        messages.error(request, "Aucune annale n'est disponible pour cette épreuve.")
        return redirect("olympiades_portail", token=token)

    form: InscriptionAnnalesForm = InscriptionAnnalesForm(request.POST or None)
    if request.method != "POST" or not form.is_valid():
        return render(
            request,
            "inscription/annales_inscrire.html",
            {
                "form": form,
                "token": token,
                "email_enseignant": email_enseignant,
                "epreuve_source": epreuve_source,
                "annales": annales_cibles,
            },
        )

    nb_equipes: int = int(form.cleaned_data["nb_equipes"])
    referent: User = epreuve_source.referent

    with transaction.atomic():
        inscription_annales, _created = InscriptionAnnales.objects.get_or_create(
            epreuve=epreuve_source,
            email_enseignant=email_enseignant,
            defaults={"nom_enseignant": ""},
        )

        preparer_groupe_et_comptes_annales(
            epreuve_source=epreuve_source,
            annales_cibles=annales_cibles,
            referent=referent,
            email_enseignant=email_enseignant,
            nb_equipes=nb_equipes,
            inscription_annales=inscription_annales,
        )

    messages.success(request, f"{nb_equipes} équipes ont été générées : elles sont inscrites à toutes les annales.")
    return redirect("olympiades_portail", token=token)


def annales_telecharger_zip(
        request: HttpRequest,
        token: str,
        inscription_annales_id: int,
) -> HttpResponse:
    """
    Télécharge un ZIP contenant un CSV par groupe associé à une inscription annales.

    Contenu :
        - un fichier CSV par groupe
        - chaque CSV contient uniquement la liste des usernames

    Sécurité :
        - token valide et non consommé
        - l'inscription annales doit appartenir à l'email du token
    """
    inscription_externe: InscriptionExterne = get_object_or_404(
        InscriptionExterne,
        token=token,
        token_est_utilise=False,
    )
    if not inscription_externe.est_valide:
        return render(request, "inscription/erreur_lien_expire.html")

    email_enseignant: str = inscription_externe.inscripteur.email

    inscription_annales: InscriptionAnnales = get_object_or_404(
        InscriptionAnnales,
        id=inscription_annales_id,
        email_enseignant=email_enseignant,
    )

    groupes: List[GroupeParticipant] = list(
        inscription_annales.groupes_associes.all().order_by("id")
    )

    buffer: io.BytesIO = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, groupe in enumerate(groupes, start=1):
            contenu_csv: io.StringIO = io.StringIO()
            writer = csv.writer(contenu_csv, delimiter=";")

            writer.writerow(["username"])
            for user in groupe.participants():
                writer.writerow([user.username])

            nom_fichier: str = f"annales_{inscription_annales.epreuve_id}_groupe_{index:03d}.csv"
            archive.writestr(nom_fichier, contenu_csv.getvalue())

    buffer.seek(0)
    nom_epreuve_fichier = inscription_annales.epreuve.nom.replace(" ", "")[:20]

    nom_zip: str = f"annales_{nom_epreuve_fichier}_{email_enseignant}.zip"
    response: HttpResponse = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{nom_zip}"'

    return response


def olympiades_mots_de_passe(request: HttpRequest, token: str) -> HttpResponse:
    """
    Page enseignant : liste les comptes (olympiades pratique + annales) que ce prof peut réinitialiser.

    Sécurité :
        - token valide / non consommé
        - la liste est calculée exclusivement à partir de (epreuve_source, email_enseignant)
    """
    inscription_externe: InscriptionExterne = get_object_or_404(
        InscriptionExterne,
        token=token,
        token_est_utilise=False,
    )
    if not inscription_externe.est_valide:
        return render(request, "inscription/erreur_lien_expire.html")

    epreuve_source: Epreuve = inscription_externe.epreuve
    email_enseignant: str = inscription_externe.inscripteur.email

    comptes = lister_comptes_resetables(epreuve_source=epreuve_source, email_enseignant=email_enseignant)

    return render(
        request,
        "inscription/olympiades_mots_de_passe.html",
        {
            "token": token,
            "epreuve": epreuve_source,
            "email_enseignant": email_enseignant,
            "users_olympiades": comptes.users_olympiades,
            "users_annales": comptes.users_annales,
        },
    )


@require_POST
def olympiades_reset_mot_de_passe(request: HttpRequest, token: str, user_id: int) -> HttpResponse:
    """
    Action POST : réinitialise le mot de passe d'un compte élève autorisé.

    Effet :
        - `set_unusable_password()` ; à la prochaine connexion, `prelogin` bascule vers `set_password`.

    Sécurité :
        - token valide / non consommé
        - le user_id doit appartenir à l'ensemble des ids autorisés pour ce token
    """
    inscription_externe: InscriptionExterne = get_object_or_404(
        InscriptionExterne,
        token=token,
        token_est_utilise=False,
    )
    if not inscription_externe.est_valide:
        return render(request, "inscription/erreur_lien_expire.html")

    epreuve_source: Epreuve = inscription_externe.epreuve
    email_enseignant: str = inscription_externe.inscripteur.email

    comptes = lister_comptes_resetables(epreuve_source=epreuve_source, email_enseignant=email_enseignant)
    if user_id not in comptes.ids_autorises:
        # Garde-fou fort : on ne révèle pas l'existence du user.
        return get_object_or_404(User, id=-1)

    utilisateur: User = get_object_or_404(User, id=user_id)
    utilisateur.set_unusable_password()
    utilisateur.save(update_fields=["password"])

    messages.success(request, f"Mot de passe réinitialisé pour {utilisateur.username}.")
    return redirect("olympiades_mots_de_passe", token=token)


def olympiades_guide(request: HttpRequest) -> HttpResponse:
    """
    Page d'aide / mode d'emploi pour les inscriptions Olympiades (côté profs).
    """
    return render(request, "inscription/olympiades_guide.html")
