from django.shortcuts import render
from django_ratelimit.decorators import ratelimit


@ratelimit(key='ip', rate='5/s', method='GET', block=True)
@ratelimit(key='ip', rate='200/m', method='GET', block=True)
@ratelimit(key='ip', rate='5000/h', method='GET', block=True)
def home(request):
    return render(request, 'accueil/accueil.html')
