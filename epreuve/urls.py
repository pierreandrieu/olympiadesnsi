from django.urls import path
from . import views

urlpatterns = [
    # Vue participant
    path("<str:hash_epreuve_id>/", views.detail_epreuve, name="detail_epreuve"),
    path("<str:hash_epreuve_id>/afficher/", views.afficher_epreuve, name="afficher_epreuve"),
    path("<str:hash_epreuve_id>/soumettre/", views.soumettre, name="soumettre"),
    # Création : pas de hashid d'exercice
    path("<str:hash_epreuve_id>/exercice/creer/", views.creer_exercice, name="creer_exercice"),

    # Édition : hashid pour l'épreuve et l'exercice
    path("<str:hash_epreuve_id>/exercice/<str:exercice_hashid>/editer/", views.editer_exercice, name="editer_exercice"),

    # Visualisation / gestion épreuve
    path("<str:hash_epreuve_id>/visualiser/", views.visualiser_epreuve_organisateur, name="visualiser_epreuve"),
    path("<str:hash_epreuve_id>/supprimer/", views.supprimer_epreuve, name="supprimer_epreuve"),
    path("<str:hash_epreuve_id>/copier/", views.copier_epreuve, name="copier_epreuve"),
    path("<str:hash_epreuve_id>/export/", views.exporter_epreuve, name="exporter_epreuve"),
    path("<str:hash_epreuve_id>/ajouter-organisateur/", views.ajouter_organisateur, name="ajouter_organisateur"),
    path("<str:hash_epreuve_id>/retirer-organisateur/<int:user_id>/", views.retirer_organisateur,
         name="supprimer_organisateur"),
    path("<str:hash_epreuve_id>/inscrire-groupes/", views.inscrire_groupes_epreuve, name="inscrire_groupes_epreuve"),
    path("<str:hash_epreuve_id>/desinscrire-groupe/<str:groupe_hashid>/", views.desinscrire_groupe_epreuve,
         name="desinscrire_groupe_epreuve"),

    # Gestion des exercices
    path("<str:hash_epreuve_id>/exercice/<str:hash_exercice_id>/supprimer/", views.supprimer_exercice, name="supprimer_exercice"),
    path("<str:hash_epreuve_id>/exercice/<str:hash_exercice_id>/assigner-jeux-de-test/", views.assigner_jeux_de_test, name="assigner_jeux_de_test"),
    path("<str:hash_epreuve_id>/exercice/<str:hash_exercice_id>/supprimer-jeux-de-test/", views.supprimer_jeux_de_test, name="supprimer_jeux_de_test"),
    path("<str:hash_epreuve_id>/exercice/<str:hash_exercice_id>/redistribuer-jeux-de-test/", views.redistribuer_jeux_de_test,
         name="redistribuer_jeux_de_test"),

    # Correction
    path("<str:hash_epreuve_id>/correction/", views.rendus_participants, name="rendus_participants"),

    # Export spécifique
    path("<str:hash_epreuve_id>/export/<str:by>/", views.export_data, name="export_data"),
]
