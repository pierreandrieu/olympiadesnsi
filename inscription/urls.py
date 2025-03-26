from django.urls import path
from . import views

urlpatterns = [
    path('confirmation-envoi/', views.confirmation_envoi_lien_email, name='confirmation_envoi_lien_email'),

    path('<str:token>/', views.inscription_par_token, name='inscription_par_token'),

    path('get_domaines/<str:hash_epreuve_id>/', views.get_domaines_for_epreuve, name='get_domaines_for_epreuve'),
    path('', views.inscription_demande, name='inscription_demande'),
]
