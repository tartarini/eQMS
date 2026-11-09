"""Every page shows the release version and commit at the top and the copyright notice at the foot."""

from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from . import workflow as wf

PW = "test-pass-123"
NOTICE = "Copyright 2026-2027 Daniele Tartarini"
RELEASE = dict(QMS_VERSION="9.9.9", QMS_COMMIT="0123456789abcdef0123456789abcdef01234567")


@override_settings(**RELEASE)
class ReleaseBannerTests(TestCase):
    def setUp(self):
        from .test_modules import make_user
        self.user = make_user("bannerqa", wf.QA)
        self.user.groups.add(Group.objects.get_or_create(name=wf.ALL_DEVICES)[0])

    def assert_banner(self, resp, name):
        html = resp.content.decode()
        self.assertEqual(resp.status_code, 200, name)
        top = html.index("v9.9.9 · 0123456")
        self.assertIn(RELEASE["QMS_COMMIT"], html, f"{name}: full commit")
        self.assertLess(top, html.index("<main") if "<main" in html else html.index('id="content"'),
                        f"{name}: version is at the top")
        self.assertGreater(html.rindex(NOTICE), top, f"{name}: copyright at the foot")

    def test_signed_out_pages(self):
        for name, url in [("login", reverse("login")), ("help", reverse("qms:help_index")),
                          ("help topic", reverse("qms:help_topic", args=["risk"]))]:
            self.assert_banner(self.client.get(url), name)

    def test_signed_in_pages(self):
        self.client.login(username="bannerqa", password=PW)
        for name in ["dashboard", "device_list", "record_list", "document_list", "my_training",
                     "hazard_list", "supplier_list", "training_matrix", "audit_log", "signing_pin"]:
            self.assert_banner(self.client.get(reverse(f"qms:{name}")), name)
        self.assert_banner(self.client.get(reverse("socialaccount_connections")), "connections")

    def test_admin_pages(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        self.client.login(username="bannerqa", password=PW)
        for url in [reverse("admin:index"), reverse("admin:qms_record_changelist")]:
            self.assert_banner(self.client.get(url), url)
        self.client.logout()
        self.assert_banner(self.client.get(reverse("admin:login")), "admin login")

    def test_unknown_commit_is_shown_as_unknown(self):
        self.client.login(username="bannerqa", password=PW)
        with override_settings(QMS_COMMIT="unknown"):
            self.assertContains(self.client.get(reverse("qms:dashboard")), "v9.9.9 · unknown")

    def test_oq_report_carries_the_notice_and_commit(self):
        from .management.commands.run_oq import _report_html
        env = {"release": "9.9.9", "git_commit": RELEASE["QMS_COMMIT"]}
        summary = {"overall": "PASS", "tests_passed": 1, "tests_run": 1, "requirements": 1,
                   "untraced_tests": []}
        html = _report_html(env, summary, [], {})
        self.assertIn(NOTICE, html)
        self.assertIn(RELEASE["QMS_COMMIT"], html)
