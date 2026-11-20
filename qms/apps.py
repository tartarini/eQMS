from django.apps import AppConfig


class QmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "qms"
    verbose_name = "SAMD_QMS"

    def ready(self):
        # QMS_* defaults are applied when qms.models is imported (see qms/models/__init__.py).
        from . import checks, signals  # noqa: F401  (register system checks and signals)
