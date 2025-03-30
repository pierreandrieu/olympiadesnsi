from typing import List

from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from epreuve.models import Epreuve
from login.utils import genere_participants_uniques
from olympiadesnsi import settings, decorators
from .forms import EquipeInscriptionForm, DemandeLienInscriptionForm
from .models import InscripteurExterne, InscriptionExterne
from inscription.utils import generate_unique_token, calculer_nombre_inscrits, save_users
from inscription.models import InscriptionDomaine, GroupeParticipant
import olympiadesnsi.constants as constantes


@ratelimit(key='ip', rate='3/s', method='GET', block=True)
@ratelimit(key='ip', rate='15/m', method='GET', block=True)
@ratelimit(key='ip', rate='50/h', method='GET', block=True)
def inscription_demande(request: HttpRequest) -> HttpResponse:
    """
    Traite la demande d'inscription en générant un token unique pour chaque inscription,
    envoie un email à l'utilisateur avec ce token.

    Args:
    - request (HttpRequest): La requête HTTP.

    Returns:
    - HttpResponse: La réponse HTTP, soit un formulaire d'inscription, soit une redirection.
    """
    if request.method == 'POST':
        form = DemandeLienInscriptionForm(request.POST)
        if form.is_valid():
            # Récupération du domaine académique et construction de l'email
            domaine: str = request.POST.get('domaine_academique')
            if "@" not in domaine:
                messages.error(request, "Il faut sélectionner le domaine de l'adresse mail")
                return redirect('inscription_demande')

            email: str = form.cleaned_data['identifiant'] + domaine
            epreuve_id: str = request.POST.get('epreuve_id')
            # Récupération ou création de l'InscripteurExterne basé sur l'email
            inscripteur, created = InscripteurExterne.objects.get_or_create(email=email)

            # Génération d'un token unique pour l'inscription
            token: str = generate_unique_token()

            # Récupération de l'objet Epreuve via son ID
            epreuve: Epreuve = Epreuve.objects.get(id=epreuve_id)

            # Création de l'objet InscriptionExterne
            inscription: InscriptionExterne = InscriptionExterne.objects.create(
                inscripteur=inscripteur,
                token=token,
                epreuve=epreuve,
                date_creation=timezone.now(),
                token_est_utilise=False
            )

            # Génération du lien d'inscription et préparation de l'email
            lien_inscription: str = request.build_absolute_uri(
                reverse('inscription_par_token', args=[inscription.token])
            )
            sujet: str = f"Lien d'inscription pour l'épreuve {epreuve.nom}"
            message: str = (
                f"Bonjour,\n\n"
                f"Veuillez utiliser le lien suivant pour inscrire des participants à l'épreuve "
                f"{epreuve.nom} :\n\n{lien_inscription}\n\n"
                f"Il vous sera demandé de renseigner le nombre d'équipes à inscrire à l'épreuve pratique.\n\n"
                f"Bien cordialement,\n"
                f"L’équipe des Olympiades de NSI"
            )

            mail = EmailMessage(
                subject=sujet,
                body=message,
                from_email=f"{settings.ADMIN_NAME} <{settings.EMAIL_HOST_USER}>",
                to=[email]
            )
            mail.send()

            # Redirection vers la page de confirmation après l'envoi de l'email
            return redirect('confirmation_envoi_lien_email')
    else:
        # Initialisation du formulaire pour une requête GET
        form: DemandeLienInscriptionForm = DemandeLienInscriptionForm()

    # Rendu du template avec le formulaire en contexte pour une requête GET ou si le formulaire n'est pas valide
    return render(request, 'inscription/demande_inscription.html', {'form': form})


@decorators.resolve_hashid_param("hash_epreuve_id", target_name="epreuve_id")
def get_domaines_for_epreuve(request: HttpRequest, epreuve_id: int)->HttpResponse:
    domaines: List[str] = list(
        InscriptionDomaine.objects
        .filter(epreuve_id=epreuve_id)
        .order_by("domaine")  # tri alphabétique
        .values_list('domaine', flat=True)
    )
    return JsonResponse(domaines, safe=False)

@ratelimit(key='ip', rate='3/s', method='GET', block=True)
@ratelimit(key='ip', rate='15/m', method='GET', block=True)
@ratelimit(key='ip', rate='50/h', method='GET', block=True)
def confirmation_envoi_lien_email(request: HttpRequest) -> HttpResponse:
    return render(request, 'inscription/confirmation_envoi_lien_inscription.html')


@ratelimit(key='ip', rate='3/s', method='GET', block=True)
@ratelimit(key='ip', rate='15/m', method='GET', block=True)
@ratelimit(key='ip', rate='50/h', method='GET', block=True)
def inscription_par_token(request: HttpRequest, token: str) -> HttpResponse:
    """
    Traite l'inscription externe d'équipes ou de participants individuels à une épreuve
    à l'aide d'un token unique. Crée ou récupère le groupe d'inscription correspondant
    et enregistre les participants.

    Args:
    request (HttpRequest): La requête HTTP envoyée à la vue.
    token (str): Le token unique associé à une inscription externe.

    Returns:
    HttpResponse: La réponse HTTP redirigeant vers une page de confirmation ou d'erreur.
    """
    try:
        inscription_externe: InscriptionExterne = InscriptionExterne.objects.get(token=token, token_est_utilise=False)
        if not inscription_externe.est_valide:
            # Si l'inscription n'est pas valide, redirige vers une page d'erreur.
            return render(request, 'inscription/erreur_lien_expire.html')

        # Étape 1 : Trouver l'InscripteurExterne et l'Epreuve.
        epreuve: Epreuve = inscription_externe.epreuve
        referent: User = epreuve.referent
        nombre_deja_inscrits: int = calculer_nombre_inscrits(epreuve, inscription_externe.inscripteur)
        max_participants_encore_possibles: int = constantes.MAX_USERS_PAR_GROUPE - nombre_deja_inscrits

        # Prépare le formulaire d'inscription avec le nombre maximum de participants possibles.
        form: EquipeInscriptionForm = EquipeInscriptionForm(request.POST or None,
                                                            max_equipes=max_participants_encore_possibles)

        if request.method == 'POST' and form.is_valid():
            nombre_participants: int = form.cleaned_data['nombre_participants']
            if nombre_participants > max_participants_encore_possibles:
                messages.error(request,f"Pour l'épreuve "
                                       f"{epreuve.nom}, il vous reste au maximum "
                               f"{max_participants_encore_possibles} inscriptions possibles."
                               f"Contactez le référent de l'épreuve en cas de problème.")
                return redirect(reverse('inscription_par_token', args=[token]))
            inscription_externe.nombre_participants_demandes = nombre_participants
            inscription_externe.save()

            # Construction de la chaîne de début
            prefix = f"auto-{epreuve.id}_{epreuve.nom[:10]}_{inscription_externe.inscripteur.email}_"

            # Compter les GroupeParticipant dont le nom commence par `prefix`
            num: int = 1 + GroupeParticipant.objects.filter(nom__startswith=prefix).count()

            groupe_participant, created = GroupeParticipant.objects.get_or_create(
                nom=f"{prefix}{num:03}",
                referent=referent,
            )
            while not created:
                num += 1
                # Crée un nouveau groupe d'inscription si nécessaire et enregistre les participants.
                groupe_participant, created = GroupeParticipant.objects.get_or_create(
                    nom=f"{prefix}{num:03}",
                    referent=referent,
                )
            groupe_participant.inscription_externe = inscription_externe
            groupe_participant.save()

            # Génère et enregistre les informations des participants.
            users_info: List[str] = genere_participants_uniques(referent, nombre_participants)
            save_users(groupe_participant.id, users_info, inscription_externe.id)

            # Marque le token comme utilisé et sauvegarde l'inscription.
            inscription_externe.token_est_utilise = True
            inscription_externe.save()

            inscription_externe.epreuve.inscrire_groupe(groupe_participant)
            # Redirige vers une page de confirmation.
            return render(request, 'inscription/confirmation_inscription_externe.html')

        # Affiche le formulaire d'inscription si GET ou POST non valide.
        return render(request, 'inscription/inscription_externe_equipes.html', {
            'form': form,
            'epreuve': epreuve.nom,
            'deja_inscrits': nombre_deja_inscrits
        })

    except InscriptionExterne.DoesNotExist:
        # Gère le cas où le token ne correspond à aucune inscription existante.
        return render(request, 'inscription/erreur_lien_expire.html')
