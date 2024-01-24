from django.urls import path
from . import views

urlpatterns = [
    path('participant/espace', views.espace_participant, name='espace_participant'),
    path('organisateur/espace', views.espace_organisateur, name='espace_organisateur'),
    path('organisateur/compte', views.gestion_compte_organisateur, name='gestion_compte_organisateur'),
    path('participant/compte', views.gestion_compte_participant, name='gestion_compte_participant'),
    path('organisateur/creer-groupe', views.creer_groupe, name='creer_groupe'),
    path('organisateur/supprimer-groupe/<int:groupe_id>/', views.supprimer_groupe, name='supprimer_groupe'),    path('organisateur/creer-epreuve', views.creer_epreuve, name='creer_epreuve'),
    path('organisateur/telecharger-csv', views.telecharger_csv, name='telecharger_csv'),
    path('organisateur/afficher-telechargement', views.afficher_page_telechargement, name='afficher_page_telechargement'),
    path('participant/compte/update', views.change_password_participant, name='change_password_participant'),
    path('organisateur/compte/update', views.change_password_organisateur, name='change_password_organisateur'),

]
