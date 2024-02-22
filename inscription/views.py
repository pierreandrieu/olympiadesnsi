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
            print("nom = ", epreuve.nom)

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
    try:
        inscription_externe = InscriptionExterne.objects.get(token=token, token_est_utilise=False)
        if inscription_externe.est_valide:

            # Étape 1 : Trouver l'InscripteurExterne et l'Epreuve
            inscripteur: InscripteurExterne = inscription_externe.inscripteur
            epreuve: Epreuve = inscription_externe.epreuve
            print("nom toto ", epreuve.nom)
            referent: User = epreuve.referent

            groupe_inscripteur: Optional[GroupeParticipant] = (
                GroupeParticipant.objects.filter(nom=f"auto_{epreuve.nom[:10]}_{inscripteur.email.split('@')[0]}",
                                                 referent=referent,
                                                 inscripteur=inscripteur).first())
            nombre_deja_inscrits: int = 0
            if groupe_inscripteur:
                nombre_deja_inscrits = groupe_inscripteur.get_nombre_participants()

            max_participants_encore_possibles = constantes.MAX_USERS_PAR_GROUPE - nombre_deja_inscrits
            form = EquipeInscriptionForm(request.POST or None,
                                         max_equipes=max_participants_encore_possibles)
            if request.method == 'POST' and form.is_valid():
                nombre_participants = form.cleaned_data['nombre_participants']
                # Ici, vous enregistreriez les informations d'inscription des équipes
                # et mettriez à jour l'objet invitation comme étant utilisé
                inscription_externe.token_est_utilise = True
                groupe_inscripteur, _ = GroupeParticipant.objects.get_or_create(
                    nom=f"auto_{epreuve.nom[:10]}_{inscripteur.email.split('@')[0]}",
                    referent=referent,
                    inscripteur=inscripteur)

                print("nom groupe = ", groupe_inscripteur.nom)
                users_info = genere_participants_uniques(referent, nombre_participants)
                save_users_task.delay(groupe_inscripteur.id, users_info, inscription_externe.id)
                inscription_externe.save()
                return redirect('confirmation_inscription_externe')
            return render(request, 'inscription/inscription_externe_equipes.html', {
                'form': form,
                'epreuve': epreuve.nom,
                'deja_inscrits': nombre_deja_inscrits
            })

    except InscriptionExterne.DoesNotExist:
        return render(request, 'inscription/erreur_lien_expire.html')

    except InscripteurExterne.DoesNotExist:
        return render(request, 'inscription/erreur_lien_expire.html')


def confirmation_inscription_externe(request: HttpRequest) -> HttpResponse:
    return render(request, 'inscription/confirmation_inscription_externe.html')


"""
def choix_epreuve(request):
    if request.method == 'POST':
        form = ChoixEpreuveForm(request.POST)
        if form.is_valid():
            epreuve_id = form.cleaned_data['epreuve'].id
            return redirect('inscription_email', epreuve_id=epreuve_id)
    else:
        form = ChoixEpreuveForm()
    return render(request, 'choix_epreuve.html', {'form': form})


def inscription_email(request, epreuve_id):
    epreuve = Epreuve.objects.get(id=epreuve_id)
    domaines = epreuve.get_domaines_autorises_list()
    domaines_choices = [(domaine, domaine) for domaine in domaines]

    if request.method == 'POST':
        form = InscriptionEmailForm(request.POST, domaines_choices=domaines_choices)
        if form.is_valid():
            # Traitement similaire à votre implémentation actuelle, en incluant l'ID de l'épreuve
            # et les domaines autorisés dans le processus
            return redirect('confirmation_envoi_lien_email')
    else:
        form = InscriptionEmailForm(domaines_choices=domaines_choices)
    return render(request, 'inscription/demande_lien_inscription_externe.html', {'form': form, 'epreuve': epreuve})


def inscription_email(request):
    if request.method == 'POST':
        form = InscriptionEmailForm(request.POST)
        if form.is_valid():
            partie_email = form.cleaned_data['email']
            domaine = form.cleaned_data['domaine_academique']
            email_complet = f"{partie_email}@{domaine}"
            # Créer une nouvelle invitation à chaque fois
            invitation = InscripteurExterne.objects.create(email=email_complet)
            inscription_link = request.build_absolute_uri(reverse('inscription_equipes', args=[invitation.token]))
            send_mail(
                'Inscription aux Olympiades NSI',
                f'Utilisez ce lien pour inscrire vos équipes: {inscription_link}',
                'pierre.andrieu@lilo.org',
                [email_complet],
                fail_silently=False,
            )
            return redirect('confirmation_envoi_lien_email')
    else:
        form = InscriptionEmailForm()
    return render(request, 'inscription/demande_lien_inscription_externe.html', {'form': form})


def confirmation_envoi_lien_email(request):
    return render(request, 'inscription/confirmation_envoi_lien_inscription.html')


def inscription_equipes(request, token):
    try:
        inscripteur = InscripteurExterne.objects.get(token=token, est_utilise=False)
        # referent_olympiades = Epreuve.objects.get()
        if inscripteur.est_valide:
            form = EquipeInscriptionForm(request.POST or None)
            if request.method == 'POST' and form.is_valid():
                # Ici, vous enregistreriez les informations d'inscription des équipes
                # et mettriez à jour l'objet invitation comme étant utilisé
                inscripteur.token_est_utilise = True
                inscripteur.save()
                return redirect('confirmation_inscription')
            return render(request, 'inscription/inscription_externe_equipes.html', {
                'form': form,
                'email': inscripteur.email,
            })
    except InscripteurExterne.DoesNotExist:
        return HttpResponse('Lien invalide ou expiré')


def confirmation_inscription(request):
    return render(request, 'inscription/confirmation_inscription.html')
    """
