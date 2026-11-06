from django.apps import AppConfig


class QmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "qms"
    verbose_name = "SAMD_QMS"

    def ready(self):
        from . import signals  # noqa: F401
