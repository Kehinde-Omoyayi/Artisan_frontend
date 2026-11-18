from django.apps import AppConfig


class frontendConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'frontend'

    def ready(self):
        # Register the startup checks (an API base URL without /api/v1 makes
        # every page look empty, so it is worth failing loudly and once).
        from . import checks  # noqa: F401
