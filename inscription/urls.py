from django.urls import path
from . import views

urlpatterns = [
    path('email/', views.inscription_email, name='inscription_email'),
    path('email/confirmation-envoi', views.confirmation_envoi_lien_email, name='confirmation_envoi_lien_email'),
    path('inscription/equipes/<str:token>/', views.inscription_equipes, name='inscription_equipes'),
]
