from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Count, Prefetch
from epreuve.models import User, Epreuve, UserEpreuve, MembreComite, Exercice
from inscription.models import GroupeParticipeAEpreuve, Inscription_domaine
from intranet.models import GroupeCreePar
from intranet.tasks import save_users_task
from epreuve.forms import EpreuveForm


@login_required
def espace_participant(request):
    if not request.user.groups.filter(name='Participant').exists():
        return HttpResponseForbidden()
    today = timezone.now()
    user = request.user
    user_groups = user.groups.all()
    group_ids = user_groups.values_list('id', flat=True)

    epreuves_ids = GroupeParticipeAEpreuve.objects.filter(groupe_id__in=group_ids).values_list('epreuve_id', flat=True)
    epreuves_user = Epreuve.objects.filter(id__in=epreuves_ids)

    # Epreuves spécifiques à l'utilisateur
    epreuves_participant = UserEpreuve.objects.filter(participant=user)

    # Classification des épreuvesv

    # Epreuves à Venir
    epreuves_a_venir = epreuves_user.filter(date_debut__gt=today)

    # Epreuves Terminées
    epreuves_terminees = epreuves_user.filter(
        Q(date_fin__lt=today) |
        Q(association_UserEpreuve_Epreuve__fin_epreuve__lt=today, association_UserEpreuve_Epreuve__participant=user)
    )

    # Epreuves en Cours (ni à venir, ni terminées)
    epreuves_en_cours = epreuves_user.exclude(
        id__in=epreuves_a_venir.values_list('id', flat=True)
    ).exclude(
        id__in=epreuves_terminees.values_list('id', flat=True)
    )

    return render(request, 'intranet/espace_participant.html', {
        'epreuves_en_cours': epreuves_en_cours,
        'epreuves_a_venir': epreuves_a_venir,
        'epreuves_terminees': epreuves_terminees,
        'epreuves_participant': epreuves_participant,
    })


@login_required
def gestion_compte_participant(request):
    if not request.user.groups.filter(name='Participant').exists():
        return HttpResponseForbidden()
    return render(request, 'intranet/gestion_compte_participant.html')


@login_required
def gestion_compte_organisateur(request):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()
    return render(request, 'intranet/gestion_compte_organisateur.html')


@login_required
def creer_groupe(request):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    if request.method == 'POST':
        nom_groupe = request.POST.get('nom_groupe')

        if len(nom_groupe) == 0:
            messages.error(request, "Le nom du groupe ne peut pas être vide.")
            return redirect('creer_groupe')

        entree_utilisateur_nb_users = str(request.POST.get('nombre_utilisateurs'))
        if not entree_utilisateur_nb_users.isdigit():
            messages.error(request, "Le champ 'nombre de participants' doit être entier")
            return redirect('creer_groupe')

        nombre_utilisateurs = int(request.POST.get('nombre_utilisateurs'))

        if not 0 < nombre_utilisateurs < 1000:
            messages.error(request, 'Le nombre de participants doit être entre 1 et 999.')
            return redirect('creer_groupe')

        groupe_existe = Group.objects.filter(name=nom_groupe).exists()
        if groupe_existe:
            messages.error(request, f'Vous avez déjà un groupe nommé {nom_groupe}.')
            return redirect('creer_groupe')

        id_createur = request.user.id
        # nombre_groupes = GroupeCreePar.objects.filter(createur_id=request.user.id).count()
        user_data = ["Username,Password"]
        users_info = []
        for i in range(1, nombre_utilisateurs + 1):
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
    return render(request, 'intranet/creer_groupe.html')


@login_required
def supprimer_groupe(request, groupe_id):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    groupe = get_object_or_404(Group, id=groupe_id)
    groupe_cree_par = GroupeCreePar.objects.get(groupe_id=groupe_id)
    if request.user.id != groupe_cree_par.createur_id:
        return HttpResponseForbidden()

    if request.method == "POST":
        # Récupérer tous les utilisateurs du groupe
        users_du_groupe = groupe.user_set.all()
        try:

            for user in users_du_groupe:
                # Vérifier si l'utilisateur appartient à d'autres groupes.
                # Par defaut, dans groupe "Participant" et dans le groupe nommé par l'organisateur
                if user.groups.count() == 2 and user.groups.filter(name="Participant").exists():
                    # Si l'utilisateur n'appartient à aucun autre groupe, le supprimer
                    user.delete()

            groupe.delete()
            messages.success(request, "Groupe supprimé avec succès.")
        except:
            messages.error(request, "Une erreur s'est produite pendant la suppression du groupe.")
        return redirect('espace_organisateur')


def telecharger_csv(request):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()
    csv_data = request.session.get('csv_data')
    nom_groupe = request.session.get('nom_groupe', 'groupe_inconnu')

    if csv_data is None:
        return redirect('espace_organisateur')

    nom_fichier = f"utilisateurs_{nom_groupe}.csv"
    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


def afficher_page_telechargement(request):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()
    return render(request, 'intranet/telecharge_csv_users.html')


@login_required
def creer_editer_epreuve(request, epreuve_id=None):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    if epreuve_id:
        epreuve = get_object_or_404(Epreuve, id=epreuve_id)
        if epreuve.referent != request.user:
            return HttpResponseForbidden()
    else:
        epreuve = None

    if request.method == 'POST':
        form = EpreuveForm(request.POST, instance=epreuve)
        if form.is_valid():
            epreuve = form.save(commit=False)
            epreuve.referent = request.user
            epreuve.save()
            form.save_m2m()

            exercice_ids_order = request.POST.getlist('exercice_order')
            for index, exercice_id in enumerate(exercice_ids_order, start=1):
                Exercice.objects.filter(id=exercice_id).update(numero=index)

            if epreuve_id is None:
                MembreComite.objects.create(epreuve=epreuve, membre=request.user)

            if epreuve.inscription_externe:
                Inscription_domaine.objects.filter(epreuve=epreuve).delete()
                domaines_str = form.cleaned_data['domaines_autorises']
                domaines_list = [d.strip() for d in domaines_str.split('\n') if d.strip().startswith('@')]
                for domaine in domaines_list:
                    Inscription_domaine.objects.create(epreuve=epreuve, domaine=domaine)

            messages.success(request, f"L'épreuve {epreuve.nom} a été {'créée' if not epreuve_id else 'mise à jour'} avec succès.")
            return redirect('espace_organisateur')
    else:
        form = EpreuveForm(instance=epreuve)

    return render(request, 'intranet/creer_epreuve.html', {
        'form': form,
        'epreuve': epreuve,
    })


@login_required
def espace_organisateur(request):
    if not request.user.groups.filter(name='Organisateur').exists():
        return HttpResponseForbidden()

    user = request.user
    groupes_crees = GroupeCreePar.objects.filter(createur=user) \
        .annotate(nombre_membres=Count('groupe__user'))

    exercice_prefetch = Prefetch('exercice_set', queryset=Exercice.objects.order_by('numero'))
    epreuves_organisees = Epreuve.objects.filter(
        comite=user  # Filtrer sur la base de l'appartenance au comité d'organisation uniquement
    ).prefetch_related(
        exercice_prefetch,
        'groupes_participants',
        Prefetch('membrecomite_set', queryset=MembreComite.objects.select_related('membre'))
    )

    epreuves_info = []
    for epreuve in epreuves_organisees:
        exercices = epreuve.exercice_set.all().order_by('numero')

        groupes_participants = epreuve.groupes_participants.all()
        participants_uniques = User.objects.filter(groups__in=groupes_participants).count()

        # Ajout du nombre de groupes, d'exercices et de membres du comité
        nombre_groupes = groupes_participants.count()
        nombre_exercices = exercices.count()
        membres_comite = [membre.membre for membre in epreuve.membrecomite_set.all()]
        nombre_organisateurs = len(membres_comite)
        epreuves_info.append((epreuve, nombre_organisateurs, groupes_participants, nombre_groupes,
                              participants_uniques, nombre_exercices, membres_comite))

    epreuve_form = EpreuveForm()

    return render(request, 'intranet/espace_organisateur.html', {
        'groupes_crees': groupes_crees,
        'epreuves_info': epreuves_info,
        'form': epreuve_form
    })


def get_unique_username(id_user: int, num: int):
    partie_alea = get_random_string(length=3, allowed_chars='abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ')
    faux_id: str = str(2 * id_user + 100)
    return f"{partie_alea}{faux_id[:len(faux_id) // 2]}_{num:03d}{faux_id[len(faux_id) // 2:]}"


@login_required
def change_password_generic(request, template: str):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important pour maintenir la session de l'utilisateur
            messages.success(request, 'Votre mot de passe a été mis à jour avec succès!')
            return render(request, template, {'form': form})
        else:
            for field in form:
                for error in field.errors:
                    messages.error(request, f"{field.label}: {error}")
            for error in form.non_field_errors():
                messages.error(request, f"Erreur: {error}")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, template, {'form': form})


@login_required
def change_password_participant(request):
    return change_password_generic(request, "intranet/gestion_compte_participant.html")


@login_required
def change_password_organisateur(request):
    return change_password_generic(request, "intranet/gestion_compte_organisateur.html")
