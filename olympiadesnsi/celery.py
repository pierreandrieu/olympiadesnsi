import os
from celery import Celery

# définir la variable d'environnement DJANGO_SETTINGS_MODULE pour le projet
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'olympiadesnsi.settings')

app = Celery('olympiadesnsi')

# Utilisation de la configuration de Django pour la configuration de Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découverte automatique des tâches asynchrones du projet
app.autodiscover_tasks(['intranet'])
