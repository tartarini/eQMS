"""System checks: does the project's configuration run SAMD_QMS as validated?

They run with every `manage.py` command, so a host platform that leaves out a middleware,
context processor, allauth adapter or URL fails at start-up rather than at run time.
"""
from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Tags, register
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.urls import NoReverseMatch, reverse

from . import integration

CHECK_TAG = "qms"


def _hint():
    return "See qms/integration.py and docs/embedding.md."


@register(CHECK_TAG)
def check_apps(app_configs, **kwargs):
    errors = []
    installed = list(settings.INSTALLED_APPS)
    for app in integration.INSTALLED_APPS:
        if not any(entry == app or entry.startswith(app + ".apps.") for entry in installed):
            errors.append(Error(f"SAMD_QMS needs {app!r} in INSTALLED_APPS.", hint=_hint(),
                                id="qms.E001"))
    if "qms" in installed and "django.forms" in installed and \
            installed.index("django.forms") < installed.index("qms"):
        errors.append(Error("'django.forms' must come after 'qms' in INSTALLED_APPS, so "
                            "SAMD_QMS's form templates are used.", hint=_hint(), id="qms.E002"))
    if getattr(settings, "FORM_RENDERER", None) != integration.FORM_RENDERER:
        errors.append(Error(f"SAMD_QMS needs FORM_RENDERER = {integration.FORM_RENDERER!r}.",
                            hint=_hint(), id="qms.E003"))
    return errors


@register(CHECK_TAG, Tags.security)
def check_middleware(app_configs, **kwargs):
    errors = []
    stack = list(settings.MIDDLEWARE)
    missing = [m for m in integration.REQUIRED_MIDDLEWARE if m not in stack]
    for m in missing:
        errors.append(Error(f"SAMD_QMS needs {m!r} in MIDDLEWARE.", hint=_hint(), id="qms.E010"))
    present = [m for m in integration.REQUIRED_MIDDLEWARE if m in stack]
    if not missing and [stack.index(m) for m in present] != sorted(stack.index(m) for m in present):
        errors.append(Error("SAMD_QMS's middleware is out of order. Required order: "
                            + ", ".join(integration.REQUIRED_MIDDLEWARE), hint=_hint(),
                            id="qms.E011"))
    return errors


@register(CHECK_TAG, Tags.templates)
def check_context_processors(app_configs, **kwargs):
    django_engines = [t for t in settings.TEMPLATES
                      if t.get("BACKEND") == "django.template.backends.django.DjangoTemplates"]
    if not django_engines:
        return [Error("SAMD_QMS needs a DjangoTemplates engine in TEMPLATES.", hint=_hint(),
                      id="qms.E020")]
    processors = django_engines[0].get("OPTIONS", {}).get("context_processors", [])
    errors = _check_admin_template()
    return errors + [Error(f"SAMD_QMS needs the context processor {p!r} in the first DjangoTemplates "
                  "engine.", hint=_hint(), id="qms.E021")
            for p in integration.REQUIRED_DJANGO_CONTEXT_PROCESSORS + integration.CONTEXT_PROCESSORS
            if p not in processors]


@register(CHECK_TAG, Tags.security)
def check_account_settings(app_configs, **kwargs):
    return [Error(f"SAMD_QMS needs {name} = {integration.ACCOUNT_SETTINGS[name]!r}; it enforces "
                  "who may sign up and sign in.", hint=_hint(), id="qms.E030")
            for name in integration.REQUIRED_ACCOUNT_SETTINGS
            if getattr(settings, name, None) != integration.ACCOUNT_SETTINGS[name]]


@register(CHECK_TAG, Tags.urls)
def check_urls(app_configs, **kwargs):
    errors = []
    for name in integration.REQUIRED_URL_NAMES:
        try:
            reverse(name)
        except NoReverseMatch:
            errors.append(Error(f"SAMD_QMS needs a URL named {name!r}.", hint=_hint(),
                                id="qms.E040"))
    return errors


def _check_admin_template():
    """Django admin pages must show the SAMD_QMS release, like every other page."""
    if "django.contrib.admin" not in settings.INSTALLED_APPS:
        return []
    try:
        origin = Path(get_template("admin/base_site.html").origin.name).resolve()
    except TemplateDoesNotExist:  # pragma: no cover - django.contrib.admin always has one
        return []
    if not any(origin.is_relative_to(d) for d in integration.TEMPLATE_DIRS):
        return [Error("Django admin does not use SAMD_QMS's admin/base_site.html, so admin pages "
                      "would not show the release. Add qms.integration.TEMPLATE_DIRS to TEMPLATES "
                      "DIRS, before any directory that overrides that template.", hint=_hint(),
                      id="qms.E022")]
    return []
