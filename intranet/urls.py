from django.urls import path
from . import views

urlpatterns = [
    # ... autres URLs ...
    path('participant/espace', views.espace_candidat, name='espace_candidat'),
    path('organisateur/espace', views.espace_organisateur, name='espace_organisateur'),
    path('organisateur/compte', views.gestion_compte, name='gestion_compte'),
    path('organisateur/creer-groupe', views.creer_groupe, name='creer_groupe'),
    path('organisateur/creer-epreuve', views.creer_epreuve, name='creer_epreuve'),
    path('organisateur/telecharger-csv', views.telecharger_csv, name='telecharger_csv'),
    path('organisateur/afficher-telechargement', views.afficher_page_telechargement, name='afficher_page_telechargement'),
]
