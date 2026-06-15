from django.apps import AppConfig


class StudioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'studio'
    verbose_name = 'Vibe-Coding Studio'

    def ready(self):
        from . import signals  # noqa: F401
