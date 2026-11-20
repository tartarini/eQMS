"""Post-market surveillance (the pms app): registration, two-factor sign-in, reports and links
to external issues. Lives in the qms package so the operational qualification runs it."""
import time
from datetime import date
from unittest import mock

from allauth.mfa.models import Authenticator
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from pms import activation
from pms.links import parse_issue_url
from pms.models import ExternalIssue, PmsProfile, Report

from .models import Device, DeviceMembership

PW = "correct-horse-battery-9"


def end_user(username="clara", user_type="clinician", active=True):
    user = User.objects.create_user(username, f"{username}@example.org", PW, is_active=active)
    PmsProfile.objects.create(user=user, user_type=user_type)
    return user


def with_authenticator(user):
    Authenticator.objects.create(user=user, type=Authenticator.Type.TOTP, data={"secret": "x"})


def sign_in(client, user, second_factor=True):
    """Signed in, with a one-time code completed in this session when second_factor is set."""
    client.force_login(user)
    if second_factor:
        session = client.session
        session["account_authentication_methods_user"] = str(user.pk)
        session["account_authentication_methods"] = [
            {"method": "password", "at": time.time(), "username": user.username},
            {"method": "mfa", "at": time.time(), "type": "totp"}]
        session.save()


def report_payload(device, **extra):
    data = {"device": device.pk, "title": "Alarm did not sound", "description": "No sound.",
            "harm": "", "contact_ok": ""}
    data.update(extra)
    return data


class LinkTests(TestCase):
    def test_github_issue_and_pull_request_links_are_recognised(self):
        self.assertEqual(parse_issue_url("https://github.com/acme/app/issues/12"),
                         ("github", "acme/app#12"))
        self.assertEqual(parse_issue_url("https://github.com/acme/app/pull/7/"),
                         ("github", "acme/app#7"))

    def test_gitlab_bitbucket_and_jira_links_are_recognised(self):
        self.assertEqual(parse_issue_url("https://gitlab.example.org/team/app/-/issues/3"),
                         ("gitlab", "team/app#3"))
        self.assertEqual(parse_issue_url("https://bitbucket.org/acme/app/issues/9"),
                         ("bitbucket", "acme/app#9"))
        self.assertEqual(parse_issue_url("https://jira.example.org/browse/QMS-41"),
                         ("jira", "QMS-41"))

    def test_other_https_links_are_kept_as_other_trackers(self):
        provider, reference = parse_issue_url("https://tracker.example.org/bugs/88")
        self.assertEqual((provider, reference), ("other", "tracker.example.org/bugs/88"))

    def test_plain_http_links_are_refused(self):
        with self.assertRaises(ValueError):
            parse_issue_url("http://github.com/acme/app/issues/12")


class RegistrationTests(TestCase):
    def register(self, **extra):
        data = {"full_name": "Clara Nurse", "email": "clara@example.org", "username": "clara",
                "user_type": "clinician", "organisation": "Ward 4", "password1": PW,
                "password2": PW, "consent": "on"}
        data.update(extra)
        return self.client.post(reverse("pms:register"), data)

    def test_registration_creates_an_inactive_account_and_sends_an_activation_link(self):
        response = self.register()
        self.assertRedirects(response, reverse("pms:activation_sent"))
        user = User.objects.get(username="clara")
        self.assertFalse(user.is_active)
        self.assertEqual(user.pms_profile.user_type, "clinician")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/pms/activate/", mail.outbox[0].body)

    def test_activation_link_activates_the_account_once(self):
        self.register()
        user = User.objects.get(username="clara")
        token = activation.activation_token(user)
        self.client.get(reverse("pms:activate", args=[token]))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        again = self.client.get(reverse("pms:activate", args=[token]))
        self.assertContains(again, "not valid")

    def test_forged_or_expired_activation_link_does_not_activate(self):
        self.register()
        user = User.objects.get(username="clara")
        self.client.get(reverse("pms:activate", args=["not-a-real-token"]))
        self.assertFalse(User.objects.get(pk=user.pk).is_active)
        with mock.patch("django.core.signing.time.time",
                        return_value=time.time() - 10 * 24 * 3600):
            token = activation.activation_token(user)
        self.client.get(reverse("pms:activate", args=[token]))
        self.assertFalse(User.objects.get(pk=user.pk).is_active)

    def test_registration_refuses_an_email_that_already_exists(self):
        end_user("someone")
        response = self.register(email="someone@example.org")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="clara").exists())


class SecondFactorTests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(name="SkinCheck", code="SKN")

    def test_surveillance_pages_need_a_signed_in_account(self):
        response = self.client.get(reverse("pms:report_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_account_without_an_authenticator_is_sent_to_set_one_up(self):
        user = end_user()
        sign_in(self.client, user, second_factor=False)
        response = self.client.get(reverse("pms:report_list"))
        self.assertTrue(response.url.startswith(reverse("mfa_activate_totp")), response.url)

    def test_account_must_enter_a_code_in_each_session(self):
        user = end_user()
        with_authenticator(user)
        sign_in(self.client, user, second_factor=False)
        response = self.client.get(reverse("pms:report_list"))
        self.assertTrue(response.url.startswith(reverse("mfa_reauthenticate")), response.url)

    def test_signed_in_with_a_code_can_use_the_pages(self):
        user = end_user()
        with_authenticator(user)
        sign_in(self.client, user)
        self.assertEqual(self.client.get(reverse("pms:report_list")).status_code, 200)


class ReportTests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(name="SkinCheck", code="SKN")
        self.clara = end_user()
        with_authenticator(self.clara)
        self.other = end_user("omar", "carer")
        with_authenticator(self.other)
        self.qa = end_user("qa_person")
        with_authenticator(self.qa)
        DeviceMembership.objects.create(device=self.device, user=self.qa, roles="QA")

    def test_end_user_sends_feedback_and_gets_a_reference(self):
        sign_in(self.client, self.clara)
        response = self.client.post(reverse("pms:report_new", args=["feedback"]),
                                    report_payload(self.device, description="Nice app."))
        report = Report.objects.get()
        self.assertRedirects(response, reverse("pms:report_detail", args=[report.number]))
        self.assertEqual(report.number, "PMS-00001")
        self.assertEqual((report.kind, report.reporter_type, report.harm), ("feedback", "clinician", "none"))

    def test_vigilance_report_needs_the_dates_and_harm(self):
        sign_in(self.client, self.clara)
        self.client.post(reverse("pms:report_new", args=["vigilance"]), report_payload(self.device))
        self.assertFalse(Report.objects.exists())
        self.client.post(reverse("pms:report_new", args=["vigilance"]),
                         report_payload(self.device, occurred_on="2026-11-01",
                                        aware_on="2026-11-02", harm="serious"))
        report = Report.objects.get()
        self.assertEqual(report.aware_on, date(2026, 11, 2))
        deadlines = dict(report.reporting_deadlines())
        self.assertEqual(deadlines["Death or unanticipated serious deterioration"], date(2026, 11, 12))
        self.assertEqual(deadlines["Serious public health threat"], date(2026, 11, 4))

    def test_reporter_sees_only_their_own_reports(self):
        sign_in(self.client, self.clara)
        self.client.post(reverse("pms:report_new", args=["complaint"]),
                         report_payload(self.device, harm="minor"))
        report = Report.objects.get()
        other = Client()
        sign_in(other, self.other)
        self.assertEqual(other.get(reverse("pms:report_detail", args=[report.number])).status_code, 404)
        self.assertNotContains(other.get(reverse("pms:report_list")), report.number)

    def test_reporter_links_an_existing_github_issue(self):
        report = Report.objects.create(kind="feedback", device=self.device, reporter=self.clara,
                                       reporter_type="clinician", title="Crash", description="x")
        sign_in(self.client, self.clara)
        url = "https://github.com/acme/skincheck/issues/12"
        self.client.post(reverse("pms:report_link_add", args=[report.number]), {"url": url})
        issue = ExternalIssue.objects.get(report=report)
        self.assertEqual((issue.provider, issue.reference), ("github", "acme/skincheck#12"))
        self.assertEqual(issue.provider_label, "GitHub")
        self.assertIn(url, self.client.get(reverse("pms:report_detail", args=[report.number])).content.decode())

    def test_qms_staff_triage_a_report(self):
        report = Report.objects.create(kind="complaint", device=self.device, reporter=self.clara,
                                       reporter_type="clinician", title="Label", description="x", harm="none")
        sign_in(self.client, self.qa)
        self.client.post(reverse("pms:triage_update", args=[report.number]), {"status": "investigating"})
        report.refresh_from_db()
        self.assertEqual(report.status, "investigating")
        self.assertEqual(self.client.get(reverse("pms:triage_list")).status_code, 200)

    def test_end_user_cannot_triage(self):
        report = Report.objects.create(kind="complaint", device=self.device, reporter=self.clara,
                                       reporter_type="clinician", title="Label", description="x", harm="none")
        sign_in(self.client, self.clara)
        self.assertEqual(self.client.get(reverse("pms:triage_list")).status_code, 403)
        self.client.post(reverse("pms:triage_update", args=[report.number]), {"status": "closed"})
        report.refresh_from_db()
        self.assertEqual(report.status, "new")
