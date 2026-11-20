# Running SAMD_QMS inside another Django project

SAMD_QMS is two Django apps, `qms` and `pms`, packaged as `samd-qms` (`pyproject.toml`). This
repository runs them standalone (`config/`, `Dockerfile`, `deploy/`). A platform can also
install them next to its own apps and share one sign-in, one database and one deployment.

The apps are developed, tested and released here, in this repository. A platform pins a
release tag, so it runs exactly the version that was validated (OQ evidence from that tag's
CI run). The platform never edits SAMD_QMS code.

## Install a release

```bash
pip install "samd-qms @ git+https://github.com/tartarini/eQMS@v1.0.0"
```

The package brings what the apps import (Django, django-allauth with MFA, python-docx,
markdown). The project chooses its own database driver, WSGI server and static file serving.
`qms.integration.MIDDLEWARE` includes WhiteNoise, so install `whitenoise` or leave it out of
your middleware list.

When you work on SAMD_QMS and a platform at the same time, install your checkout in editable
mode instead: `pip install -e ../eQMS`.

## Settings

Everything SAMD_QMS needs from a project is in `qms/integration.py`. The standalone project
(`config/settings.py`) and the test host (`tests/host_project/platform_host/settings.py`) are
built from it. Copy the test host's settings as a starting point:

```python
from qms import integration as qms_integration
from qms.sso_settings import configured_providers

INSTALLED_APPS = [
    "platform_theme",                 # optional: your template overrides, before qms
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    *qms_integration.INSTALLED_APPS,  # qms, django.forms, allauth (+ providers, mfa), pms
    "boss", "cdss",                   # the platform's other apps
]
MIDDLEWARE = qms_integration.MIDDLEWARE   # you may add entries; keep these in this order
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": qms_integration.TEMPLATE_DIRS,  # admin pages that show the SAMD_QMS release
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
globals().update(qms_integration.ACCOUNT_SETTINGS)   # allauth adapters and sign-in options
SOCIALACCOUNT_PROVIDERS = configured_providers()     # SSO_* environment variables
```

`QMS_*` settings you do not set take the defaults in `qms/conf.py` (listed in the
[settings reference](developer-guide.md#settings-reference)). Production values such as
`QMS_TWO_FACTOR`, `QMS_ADMIN_HOSTS`, `QMS_SIGNER_*` and `QMS_BASE_URL` are set by the project,
usually from the environment, as `config/settings.py` does.

`QMS_VERSION` and `QMS_COMMIT` identify the SAMD_QMS release on every page, on `/healthz` and
in the OQ report. Leave `QMS_VERSION` unset to show the installed package version
(`qms.__version__`), which a release tag always matches. If you set it, show the SAMD_QMS
release, not the platform's.

### Checks

`manage.py check` (and so every `manage.py` command) reports a project that does not run
SAMD_QMS as validated:

| Id | Problem |
| --- | --- |
| `qms.E001`, `E002` | An app from `INSTALLED_APPS` is missing, or `django.forms` comes before `qms` |
| `qms.E003` | `FORM_RENDERER` is not `TemplatesSetting` |
| `qms.E010`, `E011` | Required middleware is missing or out of order (two-factor, current user, role lens, admin host) |
| `qms.E020`, `E021` | No Django template engine, or a context processor is missing |
| `qms.E022` | Django admin does not use SAMD_QMS's `admin/base_site.html` (release identification) |
| `qms.E030` | The allauth adapters are not SAMD_QMS's (they enforce who may sign up and sign in) |
| `qms.E040` | A URL SAMD_QMS reverses is missing (`login`, `logout`, allauth, `qms:`, `pms:`) |

## URLs

SAMD_QMS expects to be at the root of the site. It provides the public landing page, sign-in
and accounts for the whole platform, and its tests assume this layout. Mount the other apps
under their own prefixes:

```python
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from qms.health import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/", include("allauth.urls")),
    path("boss/", include("boss.urls")),
    path("cdss/", include("cdss.urls")),
    path("pms/", include("pms.urls")),
    path("", include("qms.urls")),     # last: the landing page and the QMS
]
```

SAMD_QMS's own URLs are namespaced (`qms:`, `pms:`) and no page hard-codes a path, so mounting
it under a prefix also works (`tests/host_project/platform_host/prefix_urls.py`), but the
SAMD_QMS test suite and OQ run are only valid with the root layout.

## Look and navigation

Every SAMD_QMS page extends `qms/base.html`. Its header starts with
`{% include "qms/_platform_nav.html" %}`, which is empty in SAMD_QMS. To put links to the
platform's other apps there, add your own `templates/qms/_platform_nav.html` in an app listed
before `qms` (or in a `TEMPLATES` `DIRS` entry), for example:

```html
<a href="/boss/">BoSS</a> <a href="/cdss/">CDSS</a>
```

Override only that template. Replacing other SAMD_QMS templates changes validated pages.

## Users and data

- Users are `settings.AUTH_USER_MODEL` throughout (migrations and code), so the platform can
  keep Django's default user (what SAMD_QMS is tested with) and share it with its other apps.
- SAMD_QMS roles live in its own models (device teams and roles per device). Other apps keep
  their own authorisation; they must not write to SAMD_QMS tables. To raise QMS records from
  another app (for example a change request when a model is released), call the functions in
  `qms/services.py`, which apply the workflow rules, signatures and audit trail.
- The audit trail is hash-chained. Run `verify_audit` daily (`QMS_SCHEDULED_JOBS`), and in a
  replicated database make sure a failover never loses committed rows (synchronous replication).

## Scheduled jobs

`manage.py run_scheduler` runs `QMS_SCHEDULED_JOBS`. The default list holds the SAMD_QMS jobs
(`verify_audit`, `generate_pms_activities`, `send_reminders`). Add your platform's jobs, such
as its database backup, as `config/settings.py` does.

## Releasing SAMD_QMS for platforms

1. Set `__version__` in `qms/__init__.py` to the release (e.g. `1.2.0`).
2. Tag `v1.2.0`. CI refuses a tag that does not match `__version__`, runs the OQ, builds the
   image and the wheel, and installs the wheel in `tests/host_project` to run the whole suite
   there.
3. Platforms bump their pin to `@v1.2.0` and run their own CI.

Run the host-project tests locally with `make host-test`.
