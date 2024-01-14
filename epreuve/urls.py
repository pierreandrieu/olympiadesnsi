from django.urls import path
from . import views

urlpatterns = [
    # ... autres URLs ...
    path('organisateur/epreuve/<int:epreuve_id>/gerer', views.gerer_epreuve, name='gerer_epreuve'),
    path('organisateur/inscrire-epreuves/<int:id_groupe>/', views.inscrire_epreuves, name='inscrire_epreuves'),
    path('organisateur/gerer-groupe/<int:id_groupe>/', views.gerer_groupe, name='gerer_groupe'),
    path('epreuve/detail/<int:epreuve_id>/', views.detail_epreuve, name='detail_epreuve'),
    path('epreuve/afficher/<int:epreuve_id>/', views.afficher_epreuve, name='afficher_epreuve'),
    path('traiter_reponse_instance/', views.traiter_reponse_instance, name='traiter_reponse_instance'),
    path('epreuve/traiter_reponse_code/<int:exercice_id>/', views.traiter_reponse_code, name='traiter_reponse_code'),
    path('etat_exercices/<int:epreuve_id>/', views.etat_exercices, name='etat_exercices'),
]