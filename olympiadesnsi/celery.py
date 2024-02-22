import os
from celery import Celery
from django.conf import settings  # Importer les paramètres Django

# Définir la variable d'environnement DJANGO_SETTINGS_MODULE pour le projet
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'olympiadesnsi.settings')

# Initialiser une instance Celery
app = Celery('olympiadesnsi')

# Utilisation des paramètres de la base de données Django pour le broker
db_engine = settings.DATABASES['default']['ENGINE']
db_name = settings.DATABASES['default']['NAME']
db_user = settings.DATABASES['default']['USER']
db_password = settings.DATABASES['default']['PASSWORD']
db_host = settings.DATABASES['default']['HOST']
db_port = settings.DATABASES['default']['PORT']

broker_url = f'sqla+postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
app.conf.broker_url = broker_url


# Utilisation de la configuration de Django pour la configuration de Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découverte automatique des tâches asynchrones du projet
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Configuration des files d'attente
app.conf.task_default_queue = 'default'

# Paramètre supplémentaire pour gérer les tentatives de reconnexion au démarrage
app.conf.broker_connection_retry_on_startup = True
