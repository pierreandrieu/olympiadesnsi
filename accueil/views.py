from django.shortcuts import render
from django_ratelimit.decorators import ratelimit


@ratelimit(key='ip', rate='3/s', method='GET', block=True)
@ratelimit(key='ip', rate='200/m', method='GET', block=True)
@ratelimit(key='ip', rate='5000/h', method='GET', block=True)
def home(request):
    context = {
        'utilisateur_est_organisateur': request.user.groups.filter(name="Organisateur").exists(),
        'utilisateur_est_participant': request.user.groups.filter(name="Participant").exists(),
    }
    return render(request, 'accueil/accueil.html', context)
