from django.shortcuts import render
from django_ratelimit.decorators import ratelimit

from epreuve.models import Epreuve


@ratelimit(key='ip', rate='5/s', method='GET', block=True)
@ratelimit(key='ip', rate='150/m', method='GET', block=True)
@ratelimit(key='ip', rate='5000/h', method='GET', block=True)
def home(request):
    epreuves_publiques = Epreuve.objects.filter(inscription_externe=True)

    epreuves_info = [
        {"nom": epreuve.nom, "nombre_participants": epreuve.compte_participants_inscrits()}
        for epreuve in epreuves_publiques
    ]

    context = {
        'utilisateur_est_organisateur': request.user.groups.filter(name="Organisateur").exists(),
        'utilisateur_est_participant': request.user.groups.filter(name="Participant").exists(),
        'epreuves_info': epreuves_info,  # Passer la liste des noms d'épreuves et du nombre de participants
    }

    return render(request, 'accueil/accueil.html', context)