from typing import Optional, List

from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

from epreuve.models import Epreuve
from login.utils import genere_participants_uniques
from olympiadesnsi import settings
from .forms import EquipeInscriptionForm, DemandeLienInscriptionForm
from .models import InscripteurExterne, InscriptionExterne
from inscription.utils import generate_unique_token
from inscription.models import InscriptionDomaine, GroupeParticipant
import olympiadesnsi.constants as constantes
from intranet.tasks import save_users_task


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
                reverse('inscription_par_token', args=[inscription.token]))
            sujet: str = f"Lien d'inscription pour l'épreuve {epreuve.nom}"
            message: str = (f"Veuillez utiliser le lien suivant pour inscrire des participants à l'épreuve "
                            f"{epreuve.nom}: {lien_inscription}")

            # Envoi de l'email
            send_mail(sujet, message, settings.EMAIL_HOST_USER, [email])

            # Redirection vers la page de confirmation après l'envoi de l'email
            return redirect('confirmation_envoi_lien_email')
    else:
        # Initialisation du formulaire pour une requête GET
        form: DemandeLienInscriptionForm = DemandeLienInscriptionForm()

    # Rendu du template avec le formulaire en contexte pour une requête GET ou si le formulaire n'est pas valide
    return render(request, 'inscription/demande_inscription.html', {'form': form})


def get_domaines_for_epreuve(request: HttpRequest, epreuve_id: int) -> HttpResponse:
    domaines: List[InscriptionDomaine] = list(
        InscriptionDomaine.objects.filter(epreuve_id=epreuve_id).values_list('domaine', flat=True))
    return JsonResponse(list(domaines), safe=False)


def confirmation_envoi_lien_email(request: HttpRequest) -> HttpResponse:
    return render(request, 'inscription/confirmation_envoi_lien_inscription.html')


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
        inscripteur: InscripteurExterne = inscription_externe.inscripteur
        epreuve: Epreuve = inscription_externe.epreuve
        referent: User = epreuve.referent

        # Tente de trouver un groupe d'inscription existant ou crée un nouveau groupe.
        groupe_inscripteur: Optional[GroupeParticipant] = GroupeParticipant.objects.filter(
            nom=f"auto_{epreuve.nom[:10]}_{inscripteur.email.split('@')[0]}",
            referent=referent,
            inscripteur=inscripteur
        ).first()

        nombre_deja_inscrits: int = groupe_inscripteur.get_nombre_participants() if groupe_inscripteur else 0
        max_participants_encore_possibles: int = constantes.MAX_USERS_PAR_GROUPE - nombre_deja_inscrits

        # Prépare le formulaire d'inscription avec le nombre maximum de participants possibles.
        form: EquipeInscriptionForm = EquipeInscriptionForm(request.POST or None,
                                                            max_equipes=max_participants_encore_possibles)

        if request.method == 'POST' and form.is_valid():
            nombre_participants: int = form.cleaned_data['nombre_participants']
            inscription_externe.nombre_participants_demandes = nombre_participants
            inscription_externe.save()
            num: int = 1 + InscriptionExterne.objects.filter(
                epreuve=epreuve, inscripteur__email=inscripteur.email, token_est_utilise=False
            ).count()

            # Crée un nouveau groupe d'inscription si nécessaire et enregistre les participants.
            groupe_inscripteur, _ = GroupeParticipant.objects.get_or_create(
                nom=f"auto_{epreuve.nom[:10]}_{inscripteur.email}_{num:03}",
                referent=referent,
                inscripteur=inscripteur
            )

            # Génère et enregistre les informations des participants.
            users_info = genere_participants_uniques(referent, nombre_participants)
            save_users_task.delay(groupe_inscripteur.id, users_info, inscription_externe.id)

            # Marque le token comme utilisé et sauvegarde l'inscription.
            inscription_externe.token_est_utilise = True
            inscription_externe.save()

            # Redirige vers une page de confirmation.
            return redirect('confirmation_inscription_externe')

        # Affiche le formulaire d'inscription si GET ou POST non valide.
        return render(request, 'inscription/inscription_externe_equipes.html', {
            'form': form,
            'epreuve': epreuve.nom,
            'deja_inscrits': nombre_deja_inscrits
        })

    except InscriptionExterne.DoesNotExist:
        # Gère le cas où le token ne correspond à aucune inscription existante.
        return render(request, 'inscription/erreur_lien_expire.html')

    except InscripteurExterne.DoesNotExist:
        return render(request, 'inscription/erreur_lien_expire.html')


def confirmation_inscription_externe(request: HttpRequest) -> HttpResponse:
    return render(request, 'inscription/confirmation_inscription_externe.html')
