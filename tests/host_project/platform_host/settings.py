"""Settings of a host platform that installs SAMD_QMS (the qms and pms apps) from a wheel.

Everything SAMD_QMS needs comes from qms.integration; QMS_* settings keep their defaults
(qms/conf.py). This is the pattern docs/embedding.md describes.
"""
import os
from pathlib import Path

from qms import integration as qms_integration
from qms.sso_settings import configured_providers

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "host-project-tests-only"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "platform_host",  # first, so its template overrides (qms/_platform_nav.html) win
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    *qms_integration.INSTALLED_APPS,
    # A platform's own applications (e.g. "boss", "cdss") would follow here.
]
MIDDLEWARE = qms_integration.MIDDLEWARE
ROOT_URLCONF = "platform_host.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": qms_integration.TEMPLATE_DIRS,
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        *qms_integration.CONTEXT_PROCESSORS,
    ]},
}]
FORM_RENDERER = qms_integration.FORM_RENDERER
AUTHENTICATION_BACKENDS = qms_integration.AUTHENTICATION_BACKENDS
globals().update(qms_integration.ACCOUNT_SETTINGS)
SOCIALACCOUNT_PROVIDERS = configured_providers()

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                         "NAME": os.environ.get("HOST_DB", str(BASE_DIR / "host.sqlite3"))}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_TZ = True
STATIC_URL = "static/"
MEDIA_ROOT = os.environ.get("HOST_MEDIA", str(BASE_DIR / "media"))
MEDIA_URL = "/media/"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "qms:device_list"
LOGOUT_REDIRECT_URL = "login"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
