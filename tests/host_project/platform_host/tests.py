"""SAMD_QMS installed in a host project: the integration contract a platform relies on."""
from importlib.metadata import version

from django.conf import settings
from django.core.checks import run_checks
from django.test import TestCase, override_settings
from django.urls import reverse

import qms
from qms import integration


class InstalledPackageTests(TestCase):
    def test_runs_from_the_installed_package(self):
        # CI installs the wheel and runs this outside the repository: SAMD_QMS must come from
        # site-packages, not from a source checkout.
        self.assertIn("site-packages", qms.__file__)

    def test_reports_the_package_version(self):
        # The host sets no QMS_VERSION, so pages and /healthz show the installed release.
        self.assertEqual(settings.QMS_VERSION, version("samd-qms"))
        self.assertEqual(self.client.get("/healthz").json()["version"], version("samd-qms"))

    def test_qms_settings_take_their_defaults(self):
        self.assertEqual(settings.QMS_RISK_ACCEPTABLE_MAX, 4)
        self.assertTrue(settings.QMS_REQUIRE_INDEPENDENT_APPROVAL)


class PlatformNavigationTests(TestCase):
    def test_host_template_appears_in_the_header(self):
        self.assertContains(self.client.get(reverse("login")), "PLATFORM-NAV")


@override_settings(ROOT_URLCONF="platform_host.prefix_urls")
class PrefixMountTests(TestCase):
    def test_urls_follow_the_mount_point(self):
        self.assertEqual(reverse("qms:dashboard"), "/qms/")
        self.assertEqual(reverse("pms:report_list"), "/qms/pms/")

    def test_pages_work_under_a_prefix(self):
        resp = self.client.get("/qms/")  # the public landing page
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'href="{reverse("qms:access_request")}"')
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)


class ConfigurationCheckTests(TestCase):
    def errors(self):
        return {e.id for e in run_checks(tags=["qms"])}

    def test_this_project_passes(self):
        self.assertEqual(self.errors(), set())

    def test_missing_middleware_is_reported(self):
        stack = [m for m in settings.MIDDLEWARE if m != "qms.two_factor.TwoFactorMiddleware"]
        with override_settings(MIDDLEWARE=stack):
            self.assertIn("qms.E010", self.errors())

    def test_middleware_out_of_order_is_reported(self):
        stack = list(settings.MIDDLEWARE)
        i = stack.index("qms.current_user.CurrentUserMiddleware")
        j = stack.index("django.contrib.auth.middleware.AuthenticationMiddleware")
        stack[i], stack[j] = stack[j], stack[i]
        with override_settings(MIDDLEWARE=stack):
            self.assertIn("qms.E011", self.errors())

    def test_missing_context_processor_is_reported(self):
        templates = [{**settings.TEMPLATES[0], "OPTIONS": {"context_processors": [
            p for p in settings.TEMPLATES[0]["OPTIONS"]["context_processors"]
            if p != "qms.context_processors.release"]}}]
        with override_settings(TEMPLATES=templates):
            self.assertIn("qms.E021", self.errors())

    def test_admin_template_is_required(self):
        templates = [{**settings.TEMPLATES[0], "DIRS": []}]
        with override_settings(TEMPLATES=templates):
            self.assertIn("qms.E022", self.errors())

    def test_account_adapter_is_required(self):
        with override_settings(ACCOUNT_ADAPTER="allauth.account.adapter.DefaultAccountAdapter"):
            self.assertIn("qms.E030", self.errors())

    def test_missing_url_is_reported(self):
        with override_settings(ROOT_URLCONF="platform_host.no_login_urls"):
            self.assertIn("qms.E040", self.errors())

    def test_apps_are_required(self):
        apps = [a for a in settings.INSTALLED_APPS if a != "django.forms"]
        with override_settings(INSTALLED_APPS=apps):
            self.assertIn("qms.E001", {e.id for e in run_checks(tags=["qms"])})
        self.assertIn("pms", integration.INSTALLED_APPS)
