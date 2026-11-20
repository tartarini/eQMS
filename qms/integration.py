"""What a Django project needs in its settings to run SAMD_QMS (the qms and pms apps).

The standalone project (config/settings.py) is built from these values, and a host platform
uses the same ones, so both run SAMD_QMS the same way. ``manage.py check`` reports anything
missing (qms/checks.py). See docs/embedding.md.

    from qms import integration as qms_integration

    INSTALLED_APPS = [<django.contrib apps>, *qms_integration.INSTALLED_APPS, <your apps>]
    MIDDLEWARE = qms_integration.MIDDLEWARE            # or your own list in the same order
    TEMPLATES[0]["DIRS"] += qms_integration.TEMPLATE_DIRS
    TEMPLATES[0]["OPTIONS"]["context_processors"] += qms_integration.CONTEXT_PROCESSORS
    AUTHENTICATION_BACKENDS = qms_integration.AUTHENTICATION_BACKENDS
    globals().update(qms_integration.ACCOUNT_SETTINGS)
    FORM_RENDERER = qms_integration.FORM_RENDERER
"""

from pathlib import Path

# After the django.contrib apps. "django.forms" follows "qms" so that qms's form templates
# (qms/templates/django/forms/) win.
INSTALLED_APPS = [
    "qms",
    "django.forms",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.microsoft",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.orcid",
    "allauth.socialaccount.providers.openid_connect",
    "allauth.mfa",  # two-factor authentication (authenticator apps), required by the pms app
    "pms",          # post-market surveillance: feedback, complaints and vigilance reports
]

# The full middleware stack, in order. A host may add its own entries but must keep these, in
# this relative order (checked by qms.checks).
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "qms.admin_access.AdminHostMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "qms.current_user.CurrentUserMiddleware",
    "qms.role_lens.ActiveRoleMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "qms.two_factor.TwoFactorMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Middleware SAMD_QMS cannot work without, in the order they must run. (WhiteNoise and the
# security middleware are deployment choices, so they are not required.)
REQUIRED_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "qms.admin_access.AdminHostMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "qms.current_user.CurrentUserMiddleware",
    "qms.role_lens.ActiveRoleMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "qms.two_factor.TwoFactorMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# Templates that must win over other apps' (TEMPLATES DIRS, not APP_DIRS): Django admin's
# base_site.html with the SAMD_QMS version, commit and copyright (release identification).
TEMPLATE_DIRS = [Path(__file__).resolve().parent / "project_templates"]

CONTEXT_PROCESSORS = [
    "qms.context_processors.devices",
    "qms.context_processors.page_help",
    "qms.context_processors.release",
    "qms.context_processors.admin_link",
]

# Context processors from Django that the templates rely on.
REQUIRED_DJANGO_CONTEXT_PROCESSORS = [
    "django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages",
]

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"  # forms use project templates

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# django-allauth settings. The adapters enforce SAMD_QMS's account rules (who may sign up,
# verified emails, account requests), so they are required; the others are the defaults the
# validated behaviour was tested with.
ACCOUNT_SETTINGS = {
    "ACCOUNT_ADAPTER": "qms.sso.AccountAdapter",
    "SOCIALACCOUNT_ADAPTER": "qms.sso.SocialAccountAdapter",
    "ACCOUNT_LOGIN_METHODS": {"username"},
    "ACCOUNT_SIGNUP_FIELDS": ["email*", "username*"],
    "ACCOUNT_EMAIL_VERIFICATION": "none",
    "SOCIALACCOUNT_AUTO_SIGNUP": True,
    # ORCID shares no email address: an account request collects and confirms one instead.
    # Every other route to a new account still needs a verified email (see qms.sso).
    "SOCIALACCOUNT_EMAIL_REQUIRED": False,
    "SOCIALACCOUNT_EMAIL_AUTHENTICATION": True,             # match users by verified email
    "SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT": True,
    "SOCIALACCOUNT_LOGIN_ON_GET": False,                    # provider login needs a POST
    "SOCIALACCOUNT_STORE_TOKENS": False,
    "MFA_SUPPORTED_TYPES": ["totp", "recovery_codes"],
}
REQUIRED_ACCOUNT_SETTINGS = ["ACCOUNT_ADAPTER", "SOCIALACCOUNT_ADAPTER"]

# URL names the templates and views reverse outside the qms/pms namespaces. The host provides
# them: Django's LoginView/LogoutView as "login"/"logout", and allauth.urls (which names
# "socialaccount_connections", "mfa_activate_totp", "mfa_reauthenticate").
REQUIRED_URL_NAMES = ["login", "logout", "socialaccount_connections", "mfa_activate_totp",
                      "mfa_reauthenticate", "qms:dashboard", "pms:report_list"]
