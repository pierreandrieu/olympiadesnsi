from django.apps import AppConfig


class EpreuveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "epreuve"

    def ready(self) -> None:
        # Enregistre les receivers de signaux
        from . import signals  # noqa: F401


