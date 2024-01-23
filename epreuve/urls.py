from django.urls import path
from . import views

urlpatterns = [
    # ... autres URLs ...
    path('organisateur/gerer/<int:epreuve_id>/', views.gerer_epreuve, name='gerer_epreuve'),
    path('organisateur/inscrire-epreuves/<int:id_groupe>/', views.inscrire_epreuves, name='inscrire_epreuves'),
    path('organisateur/gerer-groupe/<int:id_groupe>/', views.gerer_groupe, name='gerer_groupe'),
    path('detail/<int:epreuve_id>/', views.detail_epreuve, name='detail_epreuve'),
    path('afficher/<int:epreuve_id>/', views.afficher_epreuve, name='afficher_epreuve'),
    path('soumettre_reponse/', views.soumettre, name='soumettre'),
    path('assigner-jeu-de-test/<int:exercice_id>/', views.assigner_jeu_de_test, name='assigner_jeu_de_test'),
]