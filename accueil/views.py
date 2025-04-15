from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django_ratelimit.decorators import ratelimit

from accueil.utils import get_epreuves_publiques_info


@ratelimit(key='ip', rate='5/s', method='GET', block=True)
@ratelimit(key='ip', rate='150/m', method='GET', block=True)
@ratelimit(key='ip', rate='5000/h', method='GET', block=True)
def home(request: HttpRequest) -> HttpResponse:
    context = {
        'epreuves_info': get_epreuves_publiques_info(),
    }
    return render(request, 'accueil/accueil.html', context)


@ratelimit(key='ip', rate='5/s', method='GET', block=True)
@ratelimit(key='ip', rate='150/m', method='GET', block=True)
@ratelimit(key='ip', rate='5000/h', method='GET', block=True)
def about(request: HttpRequest) -> HttpResponse:
    return render(request, 'accueil/about.html')