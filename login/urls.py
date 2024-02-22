from django.urls import path
from . import views

urlpatterns = [
    path('participant', views.login_participant, name='login_participant'),
    path('organisateur', views.login_organisateur, name='login_organisateur'),
]
