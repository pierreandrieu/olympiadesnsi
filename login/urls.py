from django.urls import path
from . import views

urlpatterns = [
    path('participant', views.login_participant, name='login_participant'),
    path('organisateur', views.login_organisateur, name='login_organisateur'),
    path('prelogin', views.prelogin, name='prelogin'),
    path('set_password/<str:username>/', views.set_password, name='set_password'),
    path('recuperation-compte', views.recuperation_compte, name='recuperation_compte'),
    path('reset-password/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(),
         name='nom_de_l_url_de_reinitialisation'),
    path('confirmation-reset-mot-de-passe/', views.confirmation_modification_mot_de_passe, name='confirmation_modification_mot_de_passe')
]
