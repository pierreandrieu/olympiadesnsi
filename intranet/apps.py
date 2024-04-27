from django.apps import AppConfig


class IntranetConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "intranet"

    def ready(self):
        # Importe les signaux pour s'assurer qu'ils sont connectés au démarrage de l'application.
        import intranet.signals
