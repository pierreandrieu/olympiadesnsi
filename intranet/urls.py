from django.urls import path
from . import views

urlpatterns = [
    # Espaces
    path('participant/espace/', views.espace_participant, name='espace_participant'),
    path('organisateur/espace/', views.espace_organisateur, name='espace_organisateur'),

    # Comptes
    path('participant/compte/', views.gestion_compte_participant, name='gestion_compte_participant'),
    path('organisateur/compte/', views.gestion_compte_organisateur, name='gestion_compte_organisateur'),
    path('participant/mot-de-passe/', views.change_password_participant, name='change_password_participant'),
    path('organisateur/mot-de-passe/', views.change_password_organisateur, name='change_password_organisateur'),

    # Groupes
    path('organisateur/groupe/creer/', views.creer_groupe, name='creer_groupe'),
    path('organisateur/groupe/<str:groupe_id>/supprimer/', views.supprimer_groupe, name='supprimer_groupe'),
    path('organisateur/groupe/<str:groupe_id>/envoyer-email/', views.envoyer_email_participants,
         name='envoyer_email_participants'),

    # Épreuves
    path('organisateur/epreuve/creer/', views.creer_epreuve, name='creer_epreuve'),
    path('organisateur/epreuve/<str:hash_epreuve_id>/editer/', views.editer_epreuve, name='editer_epreuve'),
    path('organisateur/epreuve/importer-json/', views.importer_epreuve_json, name='importer_epreuve_json'),

    # Téléchargement
    path('organisateur/telechargement/csv/', views.telecharger_csv, name='telecharger_csv'),
    path('organisateur/telechargement/', views.afficher_page_telechargement, name='afficher_page_telechargement'),

    # Utilisateurs
    path('organisateur/<str:user_id>/reset-password/', views.reset_password, name='reset_password'),
]
