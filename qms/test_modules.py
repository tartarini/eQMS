"""Tests for document control, training, risk, suppliers, attachments, notifications and SSO."""
import shutil
import tempfile
from datetime import date, timedelta
from types import SimpleNamespace

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from . import services
from . import workflow as wf
from .models import (Device, DeviceMembership, Attachment, AuditEvent, Document, DocumentVersion, Hazard,
                     ImmutableError, Record, RiskControl, Signature, SigningPin, SoupItem,
                     Supplier, TrainingAssignment, TrainingRequirement, verify_audit_chain,
                     verify_signing_credential)
from .services import TransitionError

PW = "test-pass-123"
MEDIA = tempfile.mkdtemp(prefix="qms-test-media-")


def make_user(username, role, email=None):
    user = User.objects.create_user(username, email=email or f"{username}@example.org",
                                    password=PW)
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    return user


def pdf(name="sop.pdf", content=b"%PDF-1.4 test document"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


@override_settings(MEDIA_ROOT=MEDIA)
class Base(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.device = Device(name="Test device", code="TST")
        self.device.save()
        self.eng = make_user("eng", wf.ENGINEER)
        self.qa = make_user("qa", wf.QA)
        self.qa2 = make_user("qa2", wf.QA)
        for u in User.objects.all():
            DeviceMembership.objects.create(device=self.device, user=u)


class DocumentControlTests(Base):
    def _doc_with_draft(self):
        doc = Document.objects.create(title="Software problem resolution", doc_type="SOP",
                                      owner=self.eng, review_period_months=12)
        v = services.create_version(doc, self.eng, version="1.0", change_summary="First issue",
                                    file=pdf())
        return doc, v

    def test_full_lifecycle_supersedes_and_assigns_training(self):
        doc, v1 = self._doc_with_draft()
        self.assertEqual(doc.number, "SOP-001")
        TrainingRequirement.objects.create(document=doc, group=Group.objects.get(name=wf.ENGINEER))

        services.submit_version(v1, self.eng)
        with self.assertRaisesMessage(TransitionError, "independent"):
            services.approve_version(v1, self.eng, PW)  # author, and not QA
        services.approve_version(v1, self.qa, PW)
        services.make_effective(v1, self.qa)
        v1.refresh_from_db()
        self.assertEqual(v1.status, "effective")
        from .models import add_months
        self.assertEqual(v1.next_review_date, add_months(date.today(), 12))
        self.assertTrue(TrainingAssignment.objects.filter(user=self.eng, version=v1).exists())

        # Content is frozen once submitted
        v1.change_summary = "sneaky edit"
        with self.assertRaises(ImmutableError):
            v1.save()

        # v2 supersedes v1
        doc.refresh_from_db()
        v2 = services.create_version(doc, self.qa, version="2.0", change_summary="Rewrite",
                                     file=pdf("sop2.pdf", b"%PDF-1.4 v2"))
        with self.assertRaisesMessage(TransitionError, "in progress"):
            services.create_version(doc, self.qa, version="3.0", change_summary="x", file=pdf())
        services.submit_version(v2, self.qa)
        services.approve_version(v2, self.qa2, PW)
        services.make_effective(v2, self.qa)
        v1.refresh_from_db()
        self.assertEqual(v1.status, "superseded")
        self.assertEqual(doc.effective_version, v2)
        self.assertEqual(Signature.objects.filter(object_type="Document Version").count(), 2)

    def test_submit_requires_file_and_approval_detects_tampering(self):
        doc = Document.objects.create(title="Plan", doc_type="PLAN")
        v = services.create_version(doc, self.eng, version="1.0", change_summary="x")
        with self.assertRaisesMessage(TransitionError, "Upload"):
            services.submit_version(v, self.eng)
        v.file = pdf()
        v.save()
        services.submit_version(v, self.eng)
        with open(v.file.path, "ab") as fh:  # someone edits the stored file
            fh.write(b"tampered")
        with self.assertRaisesMessage(TransitionError, "integrity"):
            services.approve_version(v, self.qa, PW)

    def test_return_needs_comment_and_obsolete_locks(self):
        doc, v = self._doc_with_draft()
        services.submit_version(v, self.eng)
        with self.assertRaises(TransitionError):
            services.return_version(v, self.qa, "")
        services.return_version(v, self.qa, "Add scope section")
        v.refresh_from_db()
        self.assertEqual(v.status, "draft")
        services.obsolete_document(doc, self.qa, PW, "Replaced by SOP-002")
        doc.refresh_from_db()
        self.assertTrue(doc.obsolete)
        doc.title = "changed"
        with self.assertRaises(ImmutableError):
            doc.save()


class TrainingTests(Base):
    def setUp(self):
        super().setUp()
        self.doc = Document.objects.create(title="Complaint handling", doc_type="SOP")
        TrainingRequirement.objects.create(document=self.doc,
                                           group=Group.objects.get(name=wf.ENGINEER))
        v = services.create_version(self.doc, self.qa, version="1.0", change_summary="x",
                                    file=pdf())
        services.submit_version(v, self.qa)
        services.approve_version(v, self.qa2, PW)
        services.make_effective(v, self.qa)
        self.version = v

    def test_complete_own_training_with_signature(self):
        a = TrainingAssignment.objects.get(user=self.eng)
        self.assertEqual(a.status, "due")
        with self.assertRaisesMessage(TransitionError, "own"):
            services.complete_training(a, self.qa, PW)
        with self.assertRaisesMessage(TransitionError, "Signature"):
            services.complete_training(a, self.eng, "wrong")
        services.complete_training(a, self.eng, PW)
        a.refresh_from_db()
        self.assertEqual(a.status, "completed")
        with self.assertRaises(ImmutableError):
            a.due_date = date.today()
            a.save()

    def test_new_joiner_gets_training_via_sync(self):
        new = make_user("newbie", wf.ENGINEER)
        self.assertFalse(TrainingAssignment.objects.filter(user=new).exists())
        services.sync_training()
        self.assertTrue(TrainingAssignment.objects.filter(user=new, version=self.version).exists())

    def test_matrix(self):
        docs, rows = services.training_matrix()
        self.assertEqual(docs, [self.doc])
        statuses = {u.username: cells[0][0] for u, cells in rows}
        self.assertEqual(statuses["eng"], "due")
        self.assertEqual(statuses["qa"], "n/a")


class RiskTests(Base):
    def _hazard(self, **kw):
        defaults = dict(title="Missed cognitive decline", hazard="Scoring model false negative",
                        harm="Delayed diagnosis", severity_initial=4, probability_initial=3)
        defaults.update(kw)
        return Hazard.objects.create(device=self.device, **defaults)

    def test_acceptance_rules(self):
        h = self._hazard()
        self.assertEqual(h.ref, "HAZ-001")
        self.assertEqual(h.initial_level, "unacceptable")  # 12
        blockers = services.hazard_acceptance_blockers(h)
        self.assertTrue(any("residual" in b for b in blockers))
        self.assertTrue(any("controls" in b for b in blockers))

        cr = Record.objects.create(device=self.device, record_type=wf.CHANGE_REQUEST, title="Add uncertainty flag")
        c = RiskControl.objects.create(hazard=h, description="Flag low-confidence results for "
                                       "clinician review", control_type="protective",
                                       implemented_by=cr)
        h.severity_residual, h.probability_residual = 4, 1
        h.save()
        self.assertEqual(h.residual_level, "acceptable")  # 4
        with self.assertRaisesMessage(TransitionError, "not verified"):
            services.accept_hazard(h, self.qa, PW)
        c.verification_evidence = "Test report TR-12"
        c.verified = True
        c.save()
        services.accept_hazard(h, self.qa, PW, "Residual risk acceptable")
        h.refresh_from_db()
        self.assertEqual(h.status, "accepted")

        h.title = "edit while accepted"
        with self.assertRaises(ImmutableError):
            h.save()
        with self.assertRaises(ImmutableError):
            RiskControl.objects.create(hazard=h, description="new", control_type="design")
        services.reopen_hazard(h, self.qa, "New complaint CMP-0003")
        h.refresh_from_db()
        self.assertEqual(h.status, "open")

    def test_alarp_residual_needs_benefit_risk(self):
        h = self._hazard(severity_initial=3, probability_initial=3)  # 9 = alarp
        RiskControl.objects.create(hazard=h, description="Label", control_type="information",
                                   verification_evidence="IFU review", verified=True)
        h.severity_residual, h.probability_residual = 3, 2  # 6 = alarp
        h.save()
        self.assertIn("benefit-risk", " ".join(services.hazard_acceptance_blockers(h)))
        h.benefit_risk_rationale = "Earlier detection outweighs residual risk"
        h.save()
        self.assertEqual(services.hazard_acceptance_blockers(h), [])

    def test_record_hazard_links_are_audited(self):
        h = self._hazard()
        pr = Record.objects.create(device=self.device, record_type=wf.PROBLEM_REPORT, title="x")
        pr.hazards.add(h)
        ev = pr.audit_events.filter(action="update").last()
        self.assertEqual(ev.changes["hazards"], {"added": ["HAZ-001"]})

    def test_matrix(self):
        self._hazard()
        grid = services.risk_matrix("initial")
        row4 = dict((s, cells) for s, cells in grid)[4]
        self.assertEqual(len(row4[2][1]), 1)  # probability 3 column


class SupplierTests(Base):
    def test_evaluation_requires_signature_and_qa(self):
        s = Supplier.objects.create(name="Cloud host", category="cloud", criticality="high",
                                    scope="Hosting")
        self.assertTrue(s.evaluation_overdue)
        with self.assertRaises(TransitionError):
            services.evaluate_supplier(s, self.eng, PW, "approved", "ISO 27001 cert reviewed")
        services.evaluate_supplier(s, self.qa, PW, "approved", "ISO 27001 cert reviewed")
        s.refresh_from_db()
        self.assertEqual(s.status, "approved")
        self.assertFalse(s.evaluation_overdue)
        s.status = "disqualified"
        with self.assertRaises(ImmutableError):
            s.save()

    def test_soup_review_overdue(self):
        item = SoupItem.objects.create(name="numpy", version="2.1", purpose="Arrays")
        self.assertTrue(item.review_overdue)
        item.last_anomaly_review = date.today()
        item.save()
        self.assertFalse(item.review_overdue)


class AttachmentTests(Base):
    def test_upload_checksum_and_immutability(self):
        self.client.login(username="eng", password=PW)
        pr = Record.objects.create(device=self.device, record_type=wf.PROBLEM_REPORT, title="x", created_by=self.eng)
        url = reverse("qms:record_attach", args=[pr.ref])
        # Must confirm no participant data
        self.client.post(url, {"file": pdf("log.txt", b"trace"), "description": "log"})
        self.assertEqual(pr.attachments.count(), 0)
        self.client.post(url, {"file": SimpleUploadedFile("evil.exe", b"MZ"),
                               "confirm_no_participant_data": "on"})
        self.assertEqual(pr.attachments.count(), 0)
        self.client.post(url, {"file": SimpleUploadedFile("log.txt", b"trace"),
                               "description": "log", "confirm_no_participant_data": "on"})
        att = pr.attachments.get()
        self.assertEqual(len(att.sha256), 64)
        self.assertTrue(att.verify())
        resp = self.client.get(reverse("qms:attachment_download", args=[att.pk]))
        self.assertEqual(b"".join(resp.streaming_content), b"trace")
        with self.assertRaises(ImmutableError):
            att.delete()
        att.description = "changed"
        with self.assertRaises(ImmutableError):
            att.save()


class NotificationTests(Base):
    def test_incident_and_assignment_emails(self):
        cso = make_user("cso", wf.CLINICAL_SAFETY)
        DeviceMembership.objects.create(device=self.device, user=cso)
        with self.captureOnCommitCallbacks(execute=True):
            inc = Record.objects.create(device=self.device, record_type=wf.INCIDENT, title="Wrong score sent to GP")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("URGENT", mail.outbox[0].subject)
        self.assertIn(cso.email, mail.outbox[0].to)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            inc.owner = self.eng
            inc.save()
        self.assertEqual(mail.outbox[0].to, [self.eng.email])

    def test_daily_reminders(self):
        Record.objects.create(device=self.device, record_type=wf.PMS_ACTIVITY, title="Trend review", owner=self.eng,
                              due_date=date.today() - timedelta(days=1))
        with self.captureOnCommitCallbacks(execute=True):
            call_command("send_reminders", stdout=open("/dev/null", "w"))
        recipients = {m.to[0] for m in mail.outbox}
        self.assertIn(self.eng.email, recipients)
        self.assertIn(self.qa.email, recipients)
        self.assertIn("OVERDUE", mail.outbox[0].body)


class SecurityTests(Base):
    def test_signing_pin_replaces_password(self):
        pin = SigningPin(user=self.qa)
        pin.set_pin("246810")
        pin.save()
        self.assertTrue(verify_signing_credential(self.qa, "246810"))
        self.assertFalse(verify_signing_credential(self.qa, PW))

    def test_sso_user_without_password_cannot_sign_without_pin(self):
        sso = User.objects.create(username="ssouser")
        sso.set_unusable_password()
        sso.save()
        self.assertFalse(verify_signing_credential(sso, ""))
        self.assertFalse(verify_signing_credential(sso, "anything"))

    def test_login_events_and_role_changes_are_audited(self):
        self.client.login(username="eng", password=PW)
        self.client.post(reverse("login"), {"username": "eng", "password": "bad"})
        self.qa.groups.add(Group.objects.get(name=wf.ENGINEER))
        events = AuditEvent.objects.filter(action="security")
        texts = [e.changes["event"] for e in events]
        self.assertIn("login", texts)
        self.assertIn("login failed", texts)
        self.assertIn("roles changed", texts)
        self.assertTrue(verify_audit_chain()[0])

    def test_user_without_role_sees_pending_page(self):
        User.objects.create_user("nobody", password=PW)
        self.client.login(username="nobody", password=PW)
        resp = self.client.get(reverse("qms:record_list"))
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "Access pending", status_code=403)


FAKE_APP = {"client_id": "test-id", "secret": "test-secret"}
PROVIDERS = {
    "google": {"APPS": [FAKE_APP], "SCOPE": ["profile", "email"]},
    "microsoft": {"APPS": [{**FAKE_APP, "settings": {"tenant": "organizations"}}]},
    "github": {"APPS": [FAKE_APP], "SCOPE": ["read:user", "user:email"]},
    "orcid": {"APPS": [FAKE_APP], "BASE_DOMAIN": "orcid.org", "MEMBER_API": False},
    "openid_connect": {"APPS": [{**FAKE_APP, "provider_id": "linkedin", "name": "LinkedIn",
                                 "settings": {"server_url": "https://www.linkedin.com/oauth"}}]},
}


@override_settings(SOCIALACCOUNT_PROVIDERS=PROVIDERS, QMS_SSO_ALLOWED_DOMAINS=["sheffield.ac.uk"])
class SSOTests(TestCase):
    def test_login_page_offers_all_five_providers(self):
        resp = self.client.get(reverse("login"))
        for name in ["Google", "Microsoft", "GitHub", "ORCID", "LinkedIn"]:
            self.assertContains(resp, f"Continue with {name}")

    def test_provider_redirects(self):
        expected = {
            "google": "accounts.google.com",
            "microsoft": "login.microsoftonline.com/organizations",
            "github": "github.com/login/oauth/authorize",
            "orcid": "orcid.org/oauth/authorize",
        }
        for provider, host in expected.items():
            resp = self.client.post(f"/accounts/{provider}/login/")
            self.assertEqual(resp.status_code, 302, provider)
            self.assertIn(host, resp["Location"], provider)
            self.assertIn("client_id=test-id", resp["Location"], provider)

    def test_get_does_not_start_login(self):
        resp = self.client.get("/accounts/google/login/")
        self.assertNotEqual(resp.status_code, 302)  # needs POST (CSRF-protected)

    def test_signup_rules(self):
        from .sso import AccountAdapter, SocialAccountAdapter, email_domain_allowed
        self.assertFalse(AccountAdapter().is_open_for_signup(None))

        def login_with(*emails, verified=True):
            return SimpleNamespace(email_addresses=[SimpleNamespace(email=e, verified=verified)
                                                    for e in emails])
        adapter = SocialAccountAdapter()
        self.assertTrue(adapter.is_open_for_signup(None, login_with("a.b@sheffield.ac.uk")))
        self.assertTrue(email_domain_allowed("x@dept.sheffield.ac.uk"))
        self.assertFalse(adapter.is_open_for_signup(None, login_with("a@gmail.com")))
        self.assertFalse(adapter.is_open_for_signup(
            None, login_with("a@sheffield.ac.uk", verified=False)))
        self.assertFalse(adapter.is_open_for_signup(None, login_with()))  # e.g. ORCID: no email
        self.assertFalse(email_domain_allowed("x@evilsheffield.ac.uk"))

    def test_provider_config_from_environment(self):
        import os
        from unittest import mock

        from .sso_settings import configured_providers
        env = {f"SSO_{p}_{k}": "v" for p in ["GOOGLE", "MICROSOFT", "GITHUB", "ORCID", "LINKEDIN"]
               for k in ["CLIENT_ID", "SECRET"]}
        with mock.patch.dict(os.environ, env, clear=False):
            providers = configured_providers()
        self.assertEqual(set(providers), {"google", "microsoft", "github", "orcid",
                                          "openid_connect"})
        self.assertEqual(providers["openid_connect"]["APPS"][0]["provider_id"], "linkedin")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(configured_providers(), {})


class ConnectedAccountsTests(TestCase):
    def setUp(self):
        self.user = make_user("conn", wf.ENGINEER)
        self.client.login(username="conn", password=PW)

    @override_settings(SOCIALACCOUNT_PROVIDERS=PROVIDERS)
    def test_page_offers_connect_buttons_for_configured_providers(self):
        resp = self.client.get(reverse("socialaccount_connections"))
        self.assertContains(resp, "Connected accounts")
        self.assertContains(resp, "No accounts connected yet")
        for name in ["Google", "Microsoft", "GitHub", "ORCID", "LinkedIn"]:
            self.assertContains(resp, f"Connect {name}")
        self.assertContains(resp, 'action="/accounts/orcid/login/?process=connect"')
        self.assertNotContains(resp, "Third-Party")

    @override_settings(SOCIALACCOUNT_PROVIDERS={})
    def test_page_explains_when_no_provider_is_switched_on(self):
        resp = self.client.get(reverse("socialaccount_connections"))
        self.assertContains(resp, "No sign-in providers are switched on")
        self.assertContains(resp, "Ask your SAMD_QMS administrator")
        self.user.is_superuser = True
        self.user.save()
        resp = self.client.get(reverse("socialaccount_connections"))
        self.assertContains(resp, "SSO_&lt;PROVIDER&gt;_CLIENT_ID")

    @override_settings(SOCIALACCOUNT_PROVIDERS=PROVIDERS)
    def test_connected_account_is_listed_and_can_be_removed(self):
        from allauth.socialaccount.models import SocialAccount
        acc = SocialAccount.objects.create(user=self.user, provider="orcid",
                                           uid="0000-0002-1825-0097")
        resp = self.client.get(reverse("socialaccount_connections"))
        self.assertContains(resp, "ORCID:")
        self.assertContains(resp, f'value="{acc.pk}"')
        resp = self.client.post(reverse("socialaccount_connections"), {"account": acc.pk})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(SocialAccount.objects.filter(pk=acc.pk).exists())


class PageTests(Base):
    def test_all_pages_render(self):
        self.qa.groups.add(Group.objects.get_or_create(name=wf.ALL_DEVICES)[0])
        doc = Document.objects.create(title="SOP", doc_type="SOP")
        services.create_version(doc, self.qa, version="1.0", change_summary="x", file=pdf())
        h = Hazard.objects.create(device=self.device, title="h", hazard="h", harm="h", severity_initial=2,
                                  probability_initial=2)
        s = Supplier.objects.create(name="S", category="cloud", criticality="low", scope="x")
        pr = Record.objects.create(device=self.device, record_type=wf.PROBLEM_REPORT, title="x")
        pr.hazards.add(h)
        self.client.login(username="qa", password=PW)
        for url in [reverse("qms:dashboard"), reverse("qms:document_list"),
                    reverse("qms:document_detail", args=[doc.number]),
                    reverse("qms:document_create"), reverse("qms:version_create",
                                                            args=[doc.number]),
                    reverse("qms:my_training"), reverse("qms:training_matrix"),
                    reverse("qms:hazard_list"), reverse("qms:hazard_detail", args=[h.ref]),
                    reverse("qms:hazard_create"), reverse("qms:control_add", args=[h.ref]),
                    reverse("qms:supplier_list"), reverse("qms:supplier_detail", args=[s.pk]),
                    reverse("qms:soup_create"), reverse("qms:audit_log"),
                    reverse("qms:audit_log") + "?kind=security",
                    reverse("qms:record_detail", args=[pr.ref]),
                    reverse("qms:record_edit", args=[pr.ref]),
                    reverse("qms:signing_pin"), reverse("socialaccount_connections")]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)

    def test_signature_by_ui(self):
        doc = Document.objects.create(title="SOP", doc_type="SOP")
        v = services.create_version(doc, self.eng, version="1.0", change_summary="x", file=pdf())
        services.submit_version(v, self.eng)
        self.client.login(username="qa", password=PW)
        self.client.post(reverse("qms:version_action", args=[v.pk, "approve"]),
                         {"password": PW, "comment": "OK"})
        v.refresh_from_db()
        self.assertEqual(v.status, "approved")
