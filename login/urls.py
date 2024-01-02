from django.urls import path
from . import views

urlpatterns = [
    path('participant/login', views.login_participant, name='login_participant'),
    path('organisateur/login', views.login_organisateur, name='login_organisateur'),
]