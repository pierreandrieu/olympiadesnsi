from django.urls import path
from . import views

urlpatterns = [
    path('detail/<int:epreuve_id>/', views.detail_epreuve, name='detail_epreuve'),
    path('afficher/<int:epreuve_id>/', views.afficher_epreuve, name='afficher_epreuve'),
    path('soumettre_reponse/', views.soumettre, name='soumettre'),
    path('<int:epreuve_id>/creer_exercice/', views.creer_editer_exercice, name='creer_exercice'),
    path('<int:epreuve_id>/editer/<int:id_exercice>/', views.creer_editer_exercice, name='editer_exercice'),
    path('<int:epreuve_id>/visualiser/', views.visualiser_epreuve_organisateur, name='visualiser_epreuve'),
    path('<int:epreuve_id>/supprimer/', views.supprimer_epreuve, name="supprimer_epreuve"),
    path('<int:epreuve_id>/ajouter_orga/', views.ajouter_organisateur, name="ajouter_organisateur"),
    path('<int:epreuve_id>/inscrire_groupes_epreuve/', views.inscrire_groupes_epreuve, name="inscrire_groupe_epreuves"),
    path('exercice/supprimer/<int:id_exercice>/', views.supprimer_exercice, name='supprimer_exercice'),
    path('exercice/assigner-jeux-de-test/<int:id_exercice>/', views.assigner_jeux_de_test, name='assigner_jeux_de_test'),
    path('exercice/supprimer-jeux-de-test/<int:id_exercice>/', views.supprimer_jeux_de_test,
         name='supprimer_jeux_de_test'),
    path('exercice/redistribuer-jeux-de-test/<int:id_exercice>/', views.redistribuer_jeux_de_test,
         name='redistribuer_jeux_de_test'),
]
