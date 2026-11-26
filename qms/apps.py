from django.conf import settings
from django.apps import AppConfig


class QmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "qms"
    verbose_name = settings.QMS_PRODUCT_NAME

    def ready(self):
        from . import signals  # noqa: F401
