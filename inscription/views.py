from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.urls import reverse
from django.http import HttpResponse
from .forms import InscriptionEmailForm, EquipeInscriptionForm
from .models import Inscripteur
from epreuve.models import Epreuve
from .forms import ChoixEpreuveForm
from intranet.models import GroupeCreePar
from intranet.tasks import save_users_task
from intranet.views import get_unique_username


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
            invitation = Inscripteur.objects.create(email=email_complet)
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
        inscripteur = Inscripteur.objects.get(token=token, est_utilise=False)
        # referent_olympiades = Epreuve.objects.get()
        if inscripteur.est_valide:
            form = EquipeInscriptionForm(request.POST or None)
            if request.method == 'POST' and form.is_valid():
                # Ici, vous enregistreriez les informations d'inscription des équipes
                # et mettriez à jour l'objet invitation comme étant utilisé
                inscripteur.est_utilise = True
                inscripteur.save()
                return redirect('confirmation_inscription')
            return render(request, 'inscription/inscription_externe_equipes.html', {
                'form': form,
                'email': inscripteur.email,
            })
    except Inscripteur.DoesNotExist:
        return HttpResponse('Lien invalide ou expiré')


def confirmation_inscription(request):
    return render(request, 'inscription/confirmation_inscription.html')
