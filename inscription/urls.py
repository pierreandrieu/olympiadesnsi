from django.urls import path
from . import views
from . import views_olympiades

urlpatterns = [
    path("confirmation-envoi/", views.confirmation_envoi_lien_email, name="confirmation_envoi_lien_email"),
    path("get_domaines/<str:hash_epreuve_id>/", views.get_domaines_for_epreuve, name="get_domaines_for_epreuve"),
    path("", views.inscription_demande, name="inscription_demande"),

    path("<str:token>/", views.inscription_par_token, name="inscription_par_token"),

    path(
        "olympiades/<str:token>/inscription/<int:inscription_id>/supprimer/",
        views_olympiades.olympiades_supprimer_inscription,
        name="olympiades_supprimer_inscription",
    ),
    # Olympiades
    path(
        "olympiades/infos-etablissement/",
        views_olympiades.olympiades_infos_etablissement,
        name="olympiades_infos_etablissement",
    ),

    path("olympiades/demande-lien/", views_olympiades.olympiades_demande_lien, name="olympiades_demande_lien"),
    path("olympiades/<str:token>/", views_olympiades.olympiades_portail, name="olympiades_portail"),
    path(
        "olympiades/<str:token>/inscription/<int:inscription_id>/zip/",
        views_olympiades.telecharger_zip_inscription,
        name="olympiades_telecharger_zip",
    ),

    path("olympiades/<str:token>/nouvelle/", views_olympiades.olympiades_nouvelle_inscription,
         name="olympiades_nouvelle_inscription"),
    path("olympiades/<str:token>/inscription/<int:inscription_id>/", views_olympiades.olympiades_editer_inscription,
         name="olympiades_editer_inscription"),

    # inscription/urls.py

    # Annales
    path(
        "olympiades/<str:token>/annales/inscrire/",
        views_olympiades.annales_inscrire,
        name="annales_inscrire",
    ),
    path(
        "olympiades/<str:token>/annales/<int:inscription_annales_id>/telecharger/",
        views_olympiades.annales_telecharger_zip,
        name="annales_telecharger_zip",
    ),
    path(
        "olympiades/<str:token>/annales/<int:inscription_annales_id>/zip/",
        views_olympiades.annales_telecharger_zip,
        name="annales_telecharger_zip",
    ),

]
