from django.urls import path
from . import views

urlpatterns = [
    path('organisateur/inscrire-epreuves/<int:id_groupe>/', views.inscrire_epreuves, name='inscrire_epreuves'),
    path('organisateur/gerer-groupe/<int:id_groupe>/', views.gerer_groupe, name='gerer_groupe'),
    path('detail/<int:epreuve_id>/', views.detail_epreuve, name='detail_epreuve'),
    path('afficher/<int:epreuve_id>/', views.afficher_epreuve, name='afficher_epreuve'),
    path('soumettre_reponse/', views.soumettre, name='soumettre'),
    path('assigner-jeu-de-test/<int:exercice_id>/', views.assigner_jeu_de_test, name='assigner_jeu_de_test'),
    path('<int:epreuve_id>/ajouter_exercice/', views.ajouter_exercice, name='ajouter_exercice'),
    path('<int:epreuve_id>/visualiser/', views.visualiser_epreuve_organisateur, name='visualiser_epreuve'),
    path('<int:epreuve_id>/editer/', views.editer_epreuve, name='editer_epreuve'),
    path('<int:epreuve_id>/supprimer/', views.supprimer_epreuve, name="supprimer_epreuve"),
    path('<int:epreuve_id>/ajouter_orga/', views.ajouter_organisateur, name="ajouter_organisateur"),
    path('<int:epreuve_id>/inscrire_groupes_epreuve/', views.inscrire_groupes_epreuve, name="inscrire_groupe_epreuves"),
    path('exercice/editer/<int:id_exercice>/', views.editer_exercice, name='editer_exercice'),
    path('exercice/supprimer/<int:id_exercice>/', views.supprimer_exercice, name='supprimer_exercice')
]
