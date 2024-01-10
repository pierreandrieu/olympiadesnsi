from django.urls import path
from . import views

urlpatterns = [
    # ... autres URLs ...
    path('organisateur/epreuve/<int:epreuve_id>/gerer', views.gerer_epreuve, name='gerer_epreuve'),
    path('organisateur/inscrire-epreuves/<int:id_groupe>/', views.inscrire_epreuves, name='inscrire_epreuves'),
    path('organisateur/gerer-groupe/<int:id_groupe>/', views.gerer_groupe, name='gerer_groupe'),
    path('epreuve/detail/<int:epreuve_id>/', views.detail_epreuve, name='detail_epreuve'),
    path('epreuve/afficher/<int:epreuve_id>/', views.afficher_epreuve, name='afficher_epreuve'),
]