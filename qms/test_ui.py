"""Interface tests: the main user journeys in a real browser (Chromium, driven by Playwright).

They run the app on a live test server and click through it as a person would, so they also
cover the HTML, JavaScript (captcha, device switcher, help popovers) and CSRF handling that the
other tests only reach through Django's test client.

Needs the development tools and a browser:

    pip install -r requirements-dev.txt
    python -m playwright install chromium

Without them these tests are skipped, and run_oq then reports URS-83 as failed: OQ evidence
must include them. Set QMS_UI_HEADED=1 to watch the browser, QMS_UI_SLOWMO=<ms> to slow it down.
"""
import os
import re
import unittest

from django.contrib.auth.models import Group
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail
from django.test import override_settings

from . import invitations
from . import workflow as wf
from .models import Device, Record, Signature
from .test_modules import PROVIDERS
from .test_roles import PW, member, person

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # development tools not installed
    sync_playwright = None

TIMEOUT_MS = 10_000


@unittest.skipIf(sync_playwright is None, "Playwright is not installed: pip install -r "
                 "requirements-dev.txt && python -m playwright install chromium")
class BrowserTestCase(StaticLiveServerTestCase):
    """A live server plus one Chromium for the class and a fresh browser context per test."""

    @classmethod
    def setUpClass(cls):
        # Playwright's sync API runs an event loop in this thread; the ORM calls the tests make
        # around it are ordinary synchronous calls.
        os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
        super().setUpClass()
        cls._pw = sync_playwright().start()
        try:
            cls.browser = cls._pw.chromium.launch(
                headless=os.environ.get("QMS_UI_HEADED") != "1",
                slow_mo=int(os.environ.get("QMS_UI_SLOWMO", "0")))
        except Exception:
            cls._pw.stop()
            super().tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._pw.stop()
        super().tearDownClass()

    def setUp(self):
        for r in wf.ROLES + (wf.ALL_DEVICES,):
            Group.objects.get_or_create(name=r)
        self.context = self.browser.new_context(base_url=self.live_server_url)
        self.context.set_default_timeout(TIMEOUT_MS)
        self.page = self.context.new_page()
        self.browser_errors = []
        self.page.on("pageerror", lambda exc: self.browser_errors.append(str(exc)))
        self.page.on("console", lambda msg: msg.type == "error"
                     and self.browser_errors.append(msg.text))
        self.addCleanup(self.context.close)

    def field(self, label, scope=None):
        """The form control with this label (not the help icon next to it, whose accessible
        name is "Help: <label>")."""
        scope = scope or self.page
        return scope.get_by_label(label).and_(self.page.locator("input, textarea, select"))

    def sign_in(self, username, password=PW):
        self.page.goto("/login/")
        self.field("Username").fill(username)
        self.field("Password").fill(password)
        self.page.get_by_role("button", name="Sign in").click()
        expect(self.page.get_by_role("button", name="Log out")).to_be_visible()

    def assertNoBrowserErrors(self):
        self.assertEqual(self.browser_errors, [], "JavaScript or console errors in the browser")


class SignInAndNavigationTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.device = Device.objects.create(name="SkinCheck", code="SKN")
        self.qa = person("qa")
        member(self.device, self.qa, wf.QA, wf.DEVICE_ADMIN)

    def test_visitor_sees_the_landing_page_and_signs_in(self):
        page = self.page
        page.goto("/")
        expect(page.get_by_role("link", name="Request an account").first).to_be_visible()
        expect(page.get_by_role("link", name="Records")).to_have_count(0)  # no QMS data
        expect(page.locator("header .release")).to_contain_text("v")
        expect(page.locator("footer.site")).to_contain_text("Copyright")
        page.get_by_role("link", name="Sign in").first.click()
        self.field("Username").fill("qa")
        self.field("Password").fill("wrong-password")
        page.get_by_role("button", name="Sign in").click()
        expect(page.locator(".errorlist, .msg.error").first).to_be_visible()
        self.sign_in("qa")
        expect(page.get_by_role("link", name="Records")).to_be_visible()
        self.assertNoBrowserErrors()

    def test_every_main_page_opens_without_browser_errors(self):
        self.sign_in("qa")
        for name in ("Dashboard", "Devices", "Records", "Documents", "Training", "Risk",
                     "Suppliers", "Invitations", "Account requests"):
            with self.subTest(page=name):
                with self.page.expect_navigation():
                    self.page.locator("header").get_by_role("link", name=name,
                                                            exact=True).click()
                expect(self.page.locator("main")).to_be_visible()
                self.assertNotIn("Server Error", self.page.content())
        self.assertNoBrowserErrors()

    def test_help_link_and_field_help_popover(self):
        self.sign_in("qa")
        self.page.goto(f"/records/new/{wf.PROBLEM_REPORT}/")
        icon = self.page.locator("button.help-icon").first
        icon.click()
        popover = self.page.locator(f"#{icon.get_attribute('popovertarget')}")
        expect(popover).to_be_visible()
        expect(popover).not_to_be_empty()
        with self.page.expect_popup() as popup:
            self.page.locator("header a.help-link").click()
        help_page = popup.value
        help_page.wait_for_load_state()
        self.assertIn("/help/", help_page.url)
        expect(help_page.locator("main")).to_contain_text("Problem")
        self.assertNoBrowserErrors()


class DeviceSwitcherTests(BrowserTestCase):
    def test_sign_in_shows_your_devices_and_opens_one(self):
        a = Device.objects.create(name="SkinCheck", code="SKN")
        b = Device.objects.create(name="RespiTrack", code="RSP")
        Device.objects.create(name="Elsewhere", code="ELS")
        dana = person("dana")
        member(a, dana, wf.QA, wf.DEVICE_ADMIN)
        member(b, dana, wf.ENGINEER)
        Record.objects.create(device=a, record_type=wf.PROBLEM_REPORT, title="Skin issue",
                              created_by=dana)
        Record.objects.create(device=b, record_type=wf.PROBLEM_REPORT, title="Respi issue",
                              created_by=dana)
        page = self.page
        self.sign_in("dana")
        expect(page).to_have_url(re.compile(r"/devices/$"))
        main = page.locator("main")
        expect(main.get_by_role("heading", name="Your devices")).to_be_visible()
        skin_row = main.locator("tr", has_text="SkinCheck")
        expect(skin_row.locator(".device-roles")).to_have_text(re.compile(r"QA\s+Device admin"))
        expect(main.locator("tr", has_text="RespiTrack").locator(".device-roles")) \
            .to_have_text("Engineer")
        expect(main).not_to_contain_text("Elsewhere")

        page.get_by_role("button", name="Open SkinCheck").click()
        expect(page).to_have_url(re.compile(r"/$"))
        expect(main).to_contain_text("Now working in the SkinCheck QMS")
        page.locator("header").get_by_role("link", name="Records", exact=True).click()
        expect(main).to_contain_text("Skin issue")
        expect(main).not_to_contain_text("Respi issue")

        page.locator("header").get_by_role("link", name="Devices", exact=True).click()
        expect(main.locator("tr", has_text="SkinCheck")).to_contain_text("Open")
        page.get_by_role("button", name="Open RespiTrack").click()
        expect(main).to_contain_text("Now working in the RespiTrack QMS")
        page.locator("header").get_by_role("link", name="Records", exact=True).click()
        expect(main).to_contain_text("Respi issue")
        expect(main).not_to_contain_text("Skin issue")
        self.assertNoBrowserErrors()

    def test_switcher_limits_the_record_list_to_one_device(self):
        a = Device.objects.create(name="SkinCheck", code="SKN")
        b = Device.objects.create(name="RespiTrack", code="RSP")
        eng = person("eng")
        member(a, eng, wf.ENGINEER)
        member(b, eng, wf.ENGINEER)
        Record.objects.create(device=a, record_type=wf.PROBLEM_REPORT, title="Skin issue",
                              created_by=eng)
        Record.objects.create(device=b, record_type=wf.PROBLEM_REPORT, title="Respi issue",
                              created_by=eng)
        self.sign_in("eng")
        self.page.goto("/records/")
        main = self.page.locator("main")
        expect(main).to_contain_text("Skin issue")
        expect(main).to_contain_text("Respi issue")
        with self.page.expect_navigation():
            self.page.locator("header").get_by_label("Device").select_option(label="RespiTrack")
        expect(main).to_contain_text("Respi issue")
        expect(main).not_to_contain_text("Skin issue")
        with self.page.expect_navigation():
            self.page.locator("header").get_by_label("Device").select_option(label="All devices")
        expect(main).to_contain_text("Skin issue")
        self.assertNoBrowserErrors()


class RecordWorkflowTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.device = Device.objects.create(name="SkinCheck", code="SKN")
        self.qa = person("qa")
        self.qa.first_name, self.qa.last_name = "Quinn", "Assurance"
        self.qa.save()
        member(self.device, self.qa, wf.QA)

    def test_problem_report_from_creation_to_a_signed_rejection(self):
        page = self.page
        self.sign_in("qa")
        page.goto(f"/records/new/{wf.PROBLEM_REPORT}/")
        main = page.locator("main")
        self.field("Device", main).select_option(label="SkinCheck")
        self.field("Title", main).fill("Classifier ignores low-light photos")
        self.field("Description", main).fill("Seen at site S03 on build 2.3.1.")
        page.locator("main").get_by_role("button").last.click()
        expect(page).to_have_url(re.compile(r"/records/PR-0001/$"))
        expect(page.locator("main")).to_contain_text("Classifier ignores low-light photos")

        reject = page.locator("form", has=page.get_by_role("button", name="Reject"))
        self.field(re.compile("Comment"), reject).fill("Duplicate of an earlier report")
        self.field("Password or signing PIN", reject).fill("not-my-password")
        reject.get_by_role("button", name="Reject").click()
        expect(page.locator("main")).to_contain_text("Signature failed")
        self.assertEqual(Record.objects.get(ref="PR-0001").status, "open")

        reject = page.locator("form", has=page.get_by_role("button", name="Reject"))
        self.field(re.compile("Comment"), reject).fill("Duplicate of an earlier report")
        self.field("Password or signing PIN", reject).fill(PW)
        reject.get_by_role("button", name="Reject").click()
        expect(page.locator("main")).to_contain_text("No further steps")
        self.assertEqual(Record.objects.get(ref="PR-0001").status, "rejected")
        sig = Signature.objects.get(record__ref="PR-0001")
        self.assertEqual(sig.signer, self.qa)
        expect(page.locator("main")).to_contain_text("Quinn Assurance")
        self.assertNoBrowserErrors()


@override_settings(SOCIALACCOUNT_PROVIDERS=PROVIDERS, QMS_CAPTCHA="pow",
                   QMS_CAPTCHA_DIFFICULTY=2000, QMS_BASE_URL="https://qms.example.org")
class RegistrationTests(BrowserTestCase):
    def test_captcha_is_solved_in_the_browser_then_providers_are_offered(self):
        page = self.page
        page.goto("/request-access/")
        expect(page.get_by_role("button", name=re.compile("Continue with"))).to_have_count(0)
        continue_button = page.locator("#captcha-continue")
        expect(continue_button).to_be_disabled()
        page.locator("#captcha-check").check()
        expect(continue_button).to_be_enabled()
        continue_button.click()
        for name in ("Google", "Microsoft", "LinkedIn", "ORCID"):
            expect(page.get_by_role("button", name=f"Continue with {name}")).to_be_visible()
        expect(page.get_by_role("button", name="Continue with GitHub")).to_have_count(0)
        self.assertNoBrowserErrors()

    def test_invitation_link_offers_only_single_sign_on(self):
        admin = person("admin")
        device = Device.objects.create(name="SkinCheck", code="SKN")
        member(device, admin, wf.DEVICE_ADMIN)
        # A live-server test commits for real, so the email is sent straight away.
        invitations.create_invitation(admin, "new.person@example.org", {device: [wf.ENGINEER]})
        path = re.search(r"https://qms\.example\.org(/invite/\S+/)", mail.outbox[-1].body).group(1)
        page = self.page
        page.goto(path)
        expect(page.locator("main")).to_contain_text("SkinCheck (SKN)")
        expect(page.get_by_role("heading", name="Register with single sign-on")).to_be_visible()
        for name in ("Google", "Microsoft", "GitHub", "LinkedIn"):
            expect(page.get_by_role("button", name=f"Continue with {name}")).to_be_visible()
        expect(page.get_by_role("button", name="Continue with ORCID")).to_have_count(0)
        expect(page.locator("input[type=password]")).to_have_count(0)
        self.assertNoBrowserErrors()
