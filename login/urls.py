from django.urls import path
from . import views

urlpatterns = [
    path("participant/", views.login_participant, name="login_participant"),
    path("organisateur/", views.login_organisateur, name="login_organisateur"),
    path("prelogin/", views.prelogin, name="prelogin"),

    path("recuperation-compte/", views.recuperation_compte, name="recuperation_compte"),
    path("set-password/<str:username>/", views.set_password, name="set_password"),
    path("reset-password/<uidb64>/<token>/", views.CustomPasswordResetConfirmView.as_view(),
         name="reset_password_confirm"),
    path("confirmation-reset-password/", views.confirmation_modification_mot_de_passe, name="reset_password_done"),
]
