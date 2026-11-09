"""The landing page and account requests: captcha, single sign-on registration, review."""
import base64
import json
import re
import time
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import AnonymousUser, Group, User
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils.html import strip_tags

from . import access_requests as ars
from . import captcha
from . import workflow as wf
from .models import AccessRequest, AuditEvent, Device, DeviceMembership
from .roles import device_roles
from .services import TransitionError
from .test_modules import PROVIDERS
from .test_roles import PW, member, person

FAST = dict(QMS_CAPTCHA_DIFFICULTY=200)


def solve_on_page(client):
    """GET the request page and solve its proof-of-work challenge, as the browser does."""
    resp = client.get(reverse("qms:access_request"))
    data = json.loads(re.search(r'id="captcha-challenge" type="application/json">(.*?)</script>',
                                resp.content.decode()).group(1))
    return captcha.solve(data)


class LandingTests(TestCase):
    def test_visitors_get_the_landing_page_in_under_300_words(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "qms/landing.html")
        main = re.search(r"<main>(.*)</main>", resp.content.decode(), re.S).group(1)
        words = strip_tags(main).split()
        self.assertLessEqual(len(words), 300)
        self.assertContains(resp, f'href="{reverse("qms:access_request")}"')
        self.assertContains(resp, f'href="{reverse("login")}"')
        self.assertContains(resp, "Google, Microsoft, LinkedIn or ORCID")

    def test_signed_in_members_get_the_dashboard(self):
        u = person("lead", wf.QA)
        self.client.login(username="lead", password=PW)
        self.assertTemplateUsed(self.client.get("/"), "qms/dashboard.html")

    def test_sign_in_page_links_to_the_request(self):
        self.assertContains(self.client.get(reverse("login")), reverse("qms:access_request"))


@override_settings(**FAST)
class CaptchaTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def request(self):
        r = self.rf.post("/")
        r.session = {}
        return r

    def test_solution_is_accepted_once(self):
        r = self.request()
        payload = captcha.solve(captcha.new_challenge(r))
        self.assertTrue(captcha.verify_pow(r, payload))
        self.assertFalse(captcha.verify_pow(r, payload))  # single use

    def test_wrong_tampered_expired_or_foreign_solutions_fail(self):
        r = self.request()
        ch = captcha.new_challenge(r)
        good = json.loads(base64.b64decode(captcha.solve(ch)))
        for bad in [{**good, "number": good["number"] + 1},
                    {**good, "signature": "0" * 64},
                    {**good, "salt": good["salt"] + "x"}]:
            captcha.new_challenge(r)
            r.session[captcha.SESSION_KEY] = ch["challenge"]
            self.assertFalse(captcha.verify_pow(r, base64.b64encode(json.dumps(bad).encode())))
        self.assertFalse(captcha.verify_pow(r, "not base64 at all"))
        other = self.request()  # a solution issued to another browser session
        self.assertFalse(captcha.verify_pow(other, captcha.solve(captcha.new_challenge(r))))
        with override_settings(QMS_CAPTCHA_TTL_SECONDS=-1):
            r2 = self.request()
            self.assertFalse(captcha.verify_pow(r2, captcha.solve(captcha.new_challenge(r2))))

    @override_settings(QMS_CAPTCHA="turnstile", QMS_TURNSTILE_SITE_KEY="site",
                       QMS_TURNSTILE_SECRET_KEY="secret")
    def test_turnstile_backend_checks_the_token_with_cloudflare(self):
        self.assertEqual(captcha.backend(), "turnstile")
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = b'{"success": true}'
        with mock.patch("urllib.request.urlopen", return_value=resp) as urlopen:
            self.assertTrue(captcha.verify_turnstile("token"))
        self.assertIn(b"secret=secret", urlopen.call_args.kwargs["data"])
        resp.__enter__.return_value.read.return_value = b'{"success": false}'
        with mock.patch("urllib.request.urlopen", return_value=resp):
            self.assertFalse(captcha.verify_turnstile("token"))
        with mock.patch("urllib.request.urlopen", side_effect=OSError):
            self.assertFalse(captcha.verify_turnstile("token"))
        self.assertFalse(captcha.verify_turnstile(""))
        page = self.client.get(reverse("qms:access_request"))
        self.assertContains(page, 'class="cf-turnstile" data-sitekey="site"')


@override_settings(SOCIALACCOUNT_PROVIDERS=PROVIDERS, **FAST)
class RegistrationTests(TestCase):
    def test_captcha_then_only_the_four_providers(self):
        page = self.client.get(reverse("qms:access_request"))
        self.assertContains(page, "I'm not a robot")
        self.assertNotContains(page, "Continue with")
        resp = self.client.post(reverse("qms:access_request"), {"captcha": "wrong"})
        self.assertContains(resp, "The check didn")
        self.assertFalse(ars.SESSION_KEY in self.client.session)
        payload = solve_on_page(self.client)
        resp = self.client.post(reverse("qms:access_request"), {"captcha": payload}, follow=True)
        for name in ["Google", "Microsoft", "LinkedIn", "ORCID"]:
            self.assertContains(resp, f"Continue with {name}")
        self.assertNotContains(resp, "Continue with GitHub")
        self.assertContains(resp, "next=%2Frequest-access%2Fdetails%2F")
        self.assertTrue(ars.captcha_passed(SimpleNamespace(session=self.client.session)))

    def test_sso_may_create_an_account_only_after_the_captcha_and_with_allowed_providers(self):
        from .sso import SocialAccountAdapter
        adapter = SocialAccountAdapter()

        def login(provider, email=None):
            return SimpleNamespace(account=SimpleNamespace(provider=provider),
                                   email_addresses=[SimpleNamespace(email=email, verified=True)]
                                   if email else [])
        fresh = SimpleNamespace(session={ars.SESSION_KEY: int(time.time())})
        stale = SimpleNamespace(session={ars.SESSION_KEY: int(time.time()) - 16 * 60})
        none = SimpleNamespace(session={})
        for provider in ["google", "microsoft", "linkedin", "orcid"]:
            self.assertTrue(adapter.is_open_for_signup(fresh, login(provider, "a@gmail.com")))
        self.assertFalse(adapter.is_open_for_signup(fresh, login("github", "a@gmail.com")))
        self.assertFalse(adapter.is_open_for_signup(stale, login("google", "a@gmail.com")))
        self.assertFalse(adapter.is_open_for_signup(none, login("orcid")))

    def test_orcid_registration_end_to_end_creates_a_roleless_account(self):
        from allauth.socialaccount.helpers import complete_social_login
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.backends.db import SessionStore
        self.client.post(reverse("qms:access_request"), {"captcha": solve_on_page(self.client)})
        request = RequestFactory().get("/accounts/orcid/login/callback/")
        request.session = SessionStore(self.client.session.session_key)
        request.user = AnonymousUser()
        request._messages = FallbackStorage(request)
        sociallogin = SocialLogin(user=User(first_name="Ada", last_name="L"),
                                  account=SocialAccount(provider="orcid",
                                                        uid="0000-0002-1825-0097"))
        sociallogin.state = {"process": "login", "next": reverse("qms:access_request_details")}
        from allauth.core import context
        with context.request_context(request):
            resp = complete_social_login(request, sociallogin)
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(socialaccount__uid="0000-0002-1825-0097")
        self.assertEqual((user.first_name, user.email), ("Ada", ""))
        self.assertFalse(user.has_usable_password())
        from .access import has_any_role
        self.assertFalse(has_any_role(user))
        self.assertTrue(AuditEvent.objects.filter(
            action="security",
            changes__event="account created via SSO for an account request").exists())
        self.assertEqual(len(mail.outbox), 0)  # QA hears when the request itself is sent

    def test_signed_in_people_skip_the_captcha(self):
        person("x")
        self.client.login(username="x", password=PW)
        self.assertRedirects(self.client.get(reverse("qms:access_request")),
                             reverse("qms:access_request_details"))


DETAILS = {"first_name": "Ada", "last_name": "Lovelace", "organisation": "Uni",
           "position": "Engineer", "devices": "Device A", "role": wf.ENGINEER,
           "reason": "Working on the analysis engine.", "agree": "on"}


@override_settings(QMS_BASE_URL="https://qms.example.org")
class RequestAndReviewTests(TestCase):
    def setUp(self):
        patcher = mock.patch("qms.notifications.transaction.on_commit", lambda f: f())
        patcher.start()
        self.addCleanup(patcher.stop)
        for r in wf.ROLES + (wf.ALL_DEVICES,):
            Group.objects.get_or_create(name=r)
        self.a = Device.objects.create(name="Device A", code="DA")
        self.b = Device.objects.create(name="Device B", code="DB")
        self.qa = person("qa_a")
        member(self.a, self.qa, wf.QA)
        self.admin_b = person("admin_b")
        member(self.b, self.admin_b, wf.DEVICE_ADMIN)
        self.eng = person("eng_a")
        member(self.a, self.eng, wf.ENGINEER)

    def newcomer(self, email="", verified=False):
        from allauth.account.models import EmailAddress
        from allauth.socialaccount.models import SocialAccount
        u = User.objects.create_user("newbie", email=email)
        u.set_unusable_password()
        u.save()
        SocialAccount.objects.create(user=u, provider="google" if email else "orcid", uid="1")
        if email:
            EmailAddress.objects.create(user=u, email=email, verified=verified, primary=True)
        self.client.force_login(u)
        return u

    def test_verified_email_goes_straight_to_review(self):
        self.newcomer("ada@uni.ac.uk", verified=True)
        page = self.client.get(reverse("qms:access_request_details"))
        self.assertContains(page, "ada@uni.ac.uk")
        self.assertNotIn("email", page.context["form"].fields)
        self.client.post(reverse("qms:access_request_details"), DETAILS)
        ar = AccessRequest.objects.get()
        self.assertEqual((ar.status, ar.email, ar.email_verified, ar.provider),
                         ("pending", "ada@uni.ac.uk", True, "google"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(set(mail.outbox[0].to),
                         {"qa_a@example.org", "admin_b@example.org"})  # managers, not engineers
        self.assertContains(self.client.get(reverse("qms:access_request_details")),
                            "waiting for review")
        self.assertTrue(AuditEvent.objects.filter(object_ref=ar.ref).exists())

    def test_orcid_email_is_confirmed_by_link_first(self):
        u = self.newcomer()
        self.client.post(reverse("qms:access_request_details"),
                         {**DETAILS, "email": "Ada@Uni.ac.uk"})
        ar = AccessRequest.objects.get()
        self.assertEqual((ar.status, ar.email, ar.email_verified), ("unconfirmed", "ada@uni.ac.uk",
                                                                    False))
        self.assertEqual(mail.outbox[0].to, ["ada@uni.ac.uk"])
        u.refresh_from_db()
        self.assertEqual(u.email, "")  # not trusted until confirmed
        with self.assertRaises(TransitionError):
            ars.approve(ar, self.qa, self.a, [wf.ENGINEER])
        link = re.search(r"https://qms.example.org(\S+)", mail.outbox[0].body).group(1)
        self.client.logout()
        self.assertContains(self.client.get(link), "is confirmed")
        ar.refresh_from_db()
        u.refresh_from_db()
        self.assertEqual((ar.status, ar.email_verified, u.email),
                         ("pending", True, "ada@uni.ac.uk"))
        self.assertEqual(len(mail.outbox), 2)  # now QA hears about it
        self.assertEqual(self.client.get(link).status_code, 200)  # reopening is harmless
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(self.client.get(link[:-3] + "xyz/").status_code, 410)

    def test_one_open_request_and_none_for_people_with_access(self):
        u = self.newcomer("ada@uni.ac.uk", verified=True)
        ars.submit(None, u, DETAILS)
        with self.assertRaises(TransitionError):
            ars.submit(None, u, DETAILS)
        self.client.force_login(self.eng)
        self.assertRedirects(self.client.get(reverse("qms:access_request_details")),
                             reverse("qms:dashboard"))

    def test_request_gives_no_access_until_approved(self):
        u = self.newcomer("ada@uni.ac.uk", verified=True)
        ars.submit(None, u, DETAILS)
        resp = self.client.get(reverse("qms:record_list"))
        self.assertContains(resp, "See or send your account request", status_code=403)

    def test_device_admin_or_qa_approves_onto_a_team_they_manage(self):
        u = self.newcomer("ada@uni.ac.uk", verified=True)
        ar = ars.submit(None, u, DETAILS)
        mail.outbox.clear()
        self.client.force_login(self.admin_b)
        page = self.client.get(reverse("qms:access_request_list"))
        self.assertContains(page, ar.ref)
        self.assertNotContains(page, "Decline and email")  # Device admin: approve only
        form = page.context["open"][0][1]
        self.assertEqual(list(form.fields["device"].queryset), [self.b])
        self.client.post(reverse("qms:access_request_approve", args=[ar.pk]),
                         {f"a{ar.pk}-device": self.a.pk, f"a{ar.pk}-roles": [wf.ENGINEER]})
        ar.refresh_from_db()
        self.assertEqual(ar.status, "pending")  # A isn't theirs
        self.client.post(reverse("qms:access_request_approve", args=[ar.pk]),
                         {f"a{ar.pk}-device": self.b.pk, f"a{ar.pk}-roles": [wf.ENGINEER]})
        ar.refresh_from_db()
        self.assertEqual((ar.status, ar.decided_by, ar.grants[0]["device"]),
                         ("approved", self.admin_b, "DB"))
        self.assertEqual(device_roles(u, self.b), {wf.ENGINEER})
        self.assertEqual(mail.outbox[-1].to, ["ada@uni.ac.uk"])
        self.assertIn("approved", mail.outbox[-1].body)
        ar.decision_note = "changed"
        with self.assertRaises(Exception):
            ar.save()
        with self.assertRaises(TransitionError):
            ars.decline(ar, self.qa, "too late")

    def test_qa_declines_with_a_reason(self):
        u = self.newcomer("ada@uni.ac.uk", verified=True)
        ar = ars.submit(None, u, DETAILS)
        with self.assertRaises(TransitionError):
            ars.decline(ar, self.admin_b, "No")  # Device admin without QA
        with self.assertRaises(TransitionError):
            ars.decline(ar, self.qa, "  ")
        self.client.force_login(self.qa)
        self.client.post(reverse("qms:access_request_decline", args=[ar.pk]),
                         {"reason": "Not on a device team here."})
        ar.refresh_from_db()
        self.assertEqual((ar.status, ar.decision_note), ("declined", "Not on a device team here."))
        self.assertIn("Not on a device team here.", mail.outbox[-1].body)
        self.assertFalse(DeviceMembership.objects.filter(user=u).exists())

    def test_list_is_for_team_managers_only(self):
        self.client.force_login(self.eng)
        self.assertRedirects(self.client.get(reverse("qms:access_request_list")),
                             reverse("qms:dashboard"))
        self.assertNotContains(self.client.get(reverse("qms:dashboard")), "Account requests")
        u = self.newcomer("ada@uni.ac.uk", verified=True)
        ars.submit(None, u, DETAILS)
        self.client.force_login(self.qa)
        self.assertContains(self.client.get(reverse("qms:dashboard")),
                            'Account requests <span class="badge warn">1</span>')
