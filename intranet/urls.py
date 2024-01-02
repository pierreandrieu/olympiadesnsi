from django.urls import path
from . import views

urlpatterns = [
    # ... autres URLs ...
    path('participant/espace', views.espace_candidat, name='espace_candidat'),
    path('organisateur/espace', views.espace_organisateur, name='espace_organisateur'),
    path('organisateur/groupes', views.gestion_groupes, name='gestion_groupes'),
    path('organisateur/epreuves', views.gestion_epreuves, name='gestion_epreuves'),
    path('organisateur/compte', views.gestion_compte, name='gestion_compte'),
    path('organisateur/creer-groupe', views.creer_groupe, name='creer_groupe'),
]