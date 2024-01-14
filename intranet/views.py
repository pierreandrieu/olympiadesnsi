from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import render
from epreuve.models import GroupeCreePar, Epreuve, GroupeParticipeAEpreuve, UserEpreuve
from django.http import HttpResponse
from django.db.models import Q
from intranet.tasks import save_users_task  # La tâche Celery pour sauvegarder les utilisateurs
from epreuve.forms import EpreuveForm
from django.utils.crypto import get_random_string
from django.utils import timezone


@login_required
def espace_candidat(request):
    today = timezone.now()
    user = request.user
    user_groups = user.groups.all()
    group_ids = user_groups.values_list('id', flat=True)

    epreuves_ids = GroupeParticipeAEpreuve.objects.filter(groupe_id__in=group_ids).values_list('epreuve_id', flat=True)
    epreuves_user = Epreuve.objects.filter(id__in=epreuves_ids)

    # Epreuves spécifiques à l'utilisateur
    epreuves_candidat = UserEpreuve.objects.filter(participant=user)

    # Classifiez les épreuves
    epreuves_en_cours = epreuves_user.filter(
        date_debut__lte=today,
        date_fin__gte=today,
        association_UserEpreuve_Epreuve__fin_epreuve__gte=today,
        association_UserEpreuve_Epreuve__participant=user
    )

    epreuves_a_venir = epreuves_user.filter(date_debut__gt=today)

    epreuves_terminees = epreuves_user.filter(
        Q(date_fin__lt=today) |
        Q(association_UserEpreuve_Epreuve__fin_epreuve__lt=today,
          association_UserEpreuve_Epreuve__participant=user)
    )

    return render(request, 'intranet/espace_candidat.html', {
        'epreuves_en_cours': epreuves_en_cours,
        'epreuves_a_venir': epreuves_a_venir,
        'epreuves_terminees': epreuves_terminees,
        'epreuves_candidat': epreuves_candidat
    })


@login_required
def gestion_compte(request):
    return render(request, 'intranet/gestion_compte.html')


@login_required
def creer_groupe(request):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    if request.method == 'POST':
        nom_groupe = request.POST.get('nom_groupe')
        entree_utilisateur_nb_users = str(request.POST.get('nombre_utilisateurs'))
        if not entree_utilisateur_nb_users.isdigit():
            messages.error(request, "Le champ 'nombre d'utilisateurs' doit etre entier")
            return redirect(reverse('espace_organisateur') + '?openModal=true')

        nombre_utilisateurs = int(request.POST.get('nombre_utilisateurs'))

        if nombre_utilisateurs >= 1000:
            messages.error(request, '999 utilisateurs max par groupe.')
            return redirect(reverse('espace_organisateur') + '?openModal=true')

        groupe_existe = Group.objects.filter(name=nom_groupe).exists()
        if groupe_existe:
            messages.error(request, 'Un groupe du même nom existe déjà.')
            return redirect(reverse('espace_organisateur') + '?openModal=true')

        id_createur = request.user.id
        # nombre_groupes = GroupeCreePar.objects.filter(createur_id=request.user.id).count()
        user_data = ["Username,Password"]
        users_info = []
        for i in range(1, nombre_utilisateurs+1):
            username = get_unique_username(id_createur, i)
            password = get_random_string(length=12,
                                         allowed_chars='abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789')
            users_info.append((username, password))
            user_data.append(f"{username},{password}")
    # Supposons que l'association GroupeCreePar doit être créée une seule fois par groupe

        # Appeler la tâche Celery pour sauvegarder les utilisateurs
        save_users_task.delay(nom_groupe, users_info, request.user.id)
        # Préparation et envoi du fichier CSV
        request.session['csv_data'] = "\n".join(user_data)
        request.session['nom_groupe'] = nom_groupe
        return redirect('afficher_page_telechargement')
    return redirect('espace_organisateur')


def telecharger_csv(request):
    csv_data = request.session.get('csv_data')
    nom_groupe = request.session.get('nom_groupe', 'groupe_inconnu')

    if csv_data is None:
        return redirect('espace_organisateur')

    nom_fichier = f"utilisateurs_{nom_groupe}.csv"
    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


# Dans views.py
def afficher_page_telechargement(request):
    return render(request, 'intranet/telecharge_csv_users.html')


@login_required
def creer_epreuve(request):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = EpreuveForm(request.POST)
        if form.is_valid():
            epreuve = form.save(commit=False)
            epreuve.referent = request.user  # Définir l'utilisateur actuel comme référent

            epreuve.save()
            form.save_m2m()  # Important pour enregistrer les relations ManyToMany

            messages.success(request, "L'épreuve a été créée avec succès.")
            return redirect('espace_organisateur')
        else:
            messages.error(request, "Il y a eu une erreur dans la création de l'épreuve.")
    else:
        form = EpreuveForm()
    return render(request, 'intranet/espace_organisateur.html', {'form': form})


@login_required
def espace_organisateur(request):
    # Récupère les groupes créés par l'utilisateur connecté
    groupes_crees = GroupeCreePar.objects.filter(createur=request.user)
    # Récupère les épreuves dont l'utilisateur est le référent
    epreuves_crees = Epreuve.objects.filter(referent=request.user)
    epreuve_form = EpreuveForm()
    return render(request, 'intranet/espace_organisateur.html', {
        'groupes_crees': groupes_crees, 'form': epreuve_form, 'epreuves_crees': epreuves_crees})


def get_unique_username(id_user: int, num: int):
    partie_alea = get_random_string(length=3, allowed_chars='abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ')
    faux_id: str = str(2 * id_user + 100)
    return f"{partie_alea}{faux_id[:len(faux_id)//2]}_{num:03d}{faux_id[len(faux_id)//2:]}"

