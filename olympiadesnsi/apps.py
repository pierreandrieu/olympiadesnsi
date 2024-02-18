from django.apps import AppConfig


class MyAppConfig(AppConfig):
    name = 'olympiadesnsi'

    def ready(self):
        import olympiadesnsi.signals
