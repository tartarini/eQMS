from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import workflow as wf
from .current_user import set_current_user
from .models import (Device, DeviceMembership, AuditEvent, ImmutableError, PMSSchedule, Record, RecordLink, Signature,
                     add_months, verify_audit_chain)
from .services import TransitionError, generate_pms_activities, perform_transition

PW = "test-pass-123"


def make_user(username, role):
    user = User.objects.create_user(username, password=PW)
    user.groups.add(Group.objects.get_or_create(name=role)[0])
    return user


class Base(TestCase):
    def setUp(self):
        self.device = Device(name="Test device", code="TST")
        self.device.save()
        self.eng = make_user("eng", wf.ENGINEER)
        self.qa = make_user("qa", wf.QA)
        self.qa2 = make_user("qa2", wf.QA)
        self.cso = make_user("cso", wf.CLINICAL_SAFETY)
        for u in User.objects.all():
            DeviceMembership.objects.create(device=self.device, user=u)

    def new(self, record_type, by=None, **fields):
        return Record.objects.create(device=self.device, record_type=record_type, title="Test",
                                     created_by=by or self.eng, **fields)


class ProblemReportWorkflowTests(Base):
    def test_full_lifecycle_with_traceability_and_signature(self):
        pr = self.new(wf.PROBLEM_REPORT)
        self.assertEqual(pr.ref, "PR-0001")
        self.assertEqual(pr.status, "open")
        perform_transition(pr, "triage", self.eng)

        with self.assertRaises(TransitionError) as ctx:
            perform_transition(pr, "assess_risk", self.eng)
        self.assertEqual(len(ctx.exception.errors), 4)  # four required fields missing

        pr.refresh_from_db()
        pr.severity, pr.patient_safety_impact = "major", "no"
        pr.software_item, pr.software_version = "ASR", "2.3.1"
        pr.save()
        perform_transition(pr, "assess_risk", self.eng)

        pr.refresh_from_db()
        pr.risk_file_updated = "pending"
        pr.save()
        with self.assertRaises(TransitionError):  # "pending" doesn't count as done
            perform_transition(pr, "start_fix", self.eng)
        pr.risk_file_updated = "not_needed"
        pr.save()
        perform_transition(pr, "start_fix", self.eng)

        with self.assertRaisesMessage(TransitionError, "fixed by Change Request"):
            perform_transition(pr, "verify", self.eng)
        cr = self.new(wf.CHANGE_REQUEST)
        RecordLink.objects.create(source=pr, target=cr, link_type="fixed_by")
        perform_transition(pr, "verify", self.eng)

        pr.refresh_from_db()
        pr.verification_evidence = "https://ci.example/run/42"
        pr.save()
        perform_transition(pr, "release", self.eng)

        with self.assertRaisesMessage(TransitionError, "Requires role"):
            perform_transition(pr, "close", self.eng, password=PW)
        with self.assertRaisesMessage(TransitionError, "password"):
            perform_transition(pr, "close", self.qa, password="wrong")
        pr = perform_transition(pr, "close", self.qa, password=PW)

        self.assertEqual(pr.status, "closed")
        self.assertIsNotNone(pr.closed_at)
        sig = Signature.objects.get(record=pr)
        self.assertEqual((sig.signer, sig.meaning), (self.qa, "Approval"))
        self.assertTrue(verify_audit_chain()[0])

    def test_reject_needs_comment(self):
        pr = self.new(wf.PROBLEM_REPORT)
        with self.assertRaisesMessage(TransitionError, "comment"):
            perform_transition(pr, "reject", self.qa, password=PW)
        pr = perform_transition(pr, "reject", self.qa, comment="Duplicate of PR-0002",
                                password=PW)
        self.assertEqual(pr.status, "rejected")

    def test_status_cannot_be_set_directly(self):
        pr = self.new(wf.PROBLEM_REPORT)
        pr.status = "closed"
        with self.assertRaises(ImmutableError):
            pr.save()

    def test_closed_records_are_locked(self):
        pr = self.new(wf.PROBLEM_REPORT)
        perform_transition(pr, "reject", self.qa, comment="Not a defect", password=PW)
        pr.refresh_from_db()
        pr.title = "Changed"
        with self.assertRaises(ImmutableError):
            pr.save()

    def test_records_cannot_be_deleted(self):
        pr = self.new(wf.PROBLEM_REPORT)
        with self.assertRaises(ImmutableError):
            pr.delete()


class IndependenceTests(Base):
    def test_author_cannot_approve_own_change(self):
        cr = self.new(wf.CHANGE_REQUEST, by=self.qa, software_item="Web app",
                      impact_analysis="Low risk", risk_file_updated="not_needed")
        perform_transition(cr, "analyse", self.qa)
        with self.assertRaisesMessage(TransitionError, "independent"):
            perform_transition(cr, "approve", self.qa, password=PW)
        cr = perform_transition(cr, "approve", self.qa2, password=PW)
        self.assertEqual(cr.status, "approved")


class ComplaintTests(Base):
    def test_reportable_complaint_needs_incident_link(self):
        c = self.new(wf.COMPLAINT, source="gp", date_aware=date.today(),
                     investigation_summary="Scoring failed", patient_safety_impact="yes")
        perform_transition(c, "investigate", self.eng)
        perform_transition(c, "decide", self.eng)
        c.refresh_from_db()
        c.reportable, c.reportability_rationale = "yes", "Risk of missed diagnosis"
        c.save()
        with self.assertRaisesMessage(TransitionError, "Incident"):
            perform_transition(c, "close", self.cso, password=PW)
        inc = self.new(wf.INCIDENT)
        RecordLink.objects.create(source=c, target=inc, link_type="escalated_to")
        c = perform_transition(c, "close", self.cso, password=PW)
        self.assertEqual(c.status, "closed")

    def test_date_aware_cannot_be_future(self):
        c = Record(device=self.device, record_type=wf.COMPLAINT, title="x",
                   date_aware=date.today() + timedelta(days=1))
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            c.full_clean()


class IncidentTests(Base):
    def test_report_due_and_overdue(self):
        aware = date.today() - timedelta(days=12)
        inc = self.new(wf.INCIDENT, date_aware=aware,
                       deadline_category="death_or_serious_deterioration")
        self.assertEqual(inc.report_due, aware + timedelta(days=10))
        self.assertTrue(inc.is_overdue)


class AuditTests(Base):
    def test_changes_are_logged_with_actor(self):
        token = set_current_user(self.eng)
        try:
            pr = Record.objects.create(device=self.device, record_type=wf.PROBLEM_REPORT, title="Before")
            pr.title = "After"
            pr.save()
        finally:
            from .current_user import _current_user
            _current_user.reset(token)
        update = pr.audit_events.get(action="update")
        self.assertEqual(update.changes["title"], ["Before", "After"])
        self.assertEqual(update.actor, self.eng)
        self.assertEqual(pr.created_by, self.eng)

    def test_audit_events_are_immutable(self):
        pr = self.new(wf.PROBLEM_REPORT)
        event = pr.audit_events.first()
        event.comment = "edited"
        with self.assertRaises(ImmutableError):
            event.save()
        with self.assertRaises(ImmutableError):
            event.delete()
        with self.assertRaises(ImmutableError):
            AuditEvent.objects.all().delete()
        with self.assertRaises(ImmutableError):
            AuditEvent.objects.update(comment="x")

    def test_tampering_is_detected(self):
        pr = self.new(wf.PROBLEM_REPORT)
        perform_transition(pr, "triage", self.eng)
        self.assertTrue(verify_audit_chain()[0])
        # Simulate someone editing the database directly, bypassing the ORM guards.
        from django.db import connection
        event = AuditEvent.objects.order_by("id").first()
        with connection.cursor() as cur:
            cur.execute("UPDATE qms_auditevent SET comment = %s WHERE id = %s",
                        ["tampered", event.id])
        ok, bad_id = verify_audit_chain()
        self.assertFalse(ok)
        self.assertEqual(bad_id, event.id)

    def test_signatures_are_immutable(self):
        pr = self.new(wf.PROBLEM_REPORT)
        pr = perform_transition(pr, "reject", self.qa, comment="dup", password=PW)
        sig = pr.signatures.get()
        with self.assertRaises(ImmutableError):
            sig.delete()


class PMSTests(Base):
    def test_generation_is_idempotent_and_advances(self):
        today = date(2026, 11, 5)
        sched = PMSSchedule.objects.create(device=self.device, name="Trend review", cadence_months=3,
                                           next_due=date(2026, 11, 30))
        created = generate_pms_activities(today=today, horizon_days=30)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].due_date, date(2026, 11, 30))
        self.assertEqual(created[0].status, "todo")
        sched.refresh_from_db()
        self.assertEqual(sched.next_due, date(2027, 2, 28))
        self.assertEqual(generate_pms_activities(today=today, horizon_days=30), [])

    def test_add_months_month_end(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2026, 11, 30), 3), date(2027, 2, 28))
        self.assertEqual(add_months(date(2026, 2, 28), 1), date(2026, 3, 31))
        self.assertEqual(add_months(date(2026, 3, 15), 12), date(2027, 3, 15))

    def test_seed_command(self):
        call_command("seed_qms", "--demo", stdout=open("/dev/null", "w"))
        self.assertEqual(PMSSchedule.objects.count(), 9)
        self.assertTrue(User.objects.filter(username="qa", groups__name=wf.QA).exists())


class ViewTests(Base):
    def test_pages_render_and_transition_via_ui(self):
        self.client.login(username="eng", password=PW)
        self.assertEqual(self.client.get(reverse("qms:dashboard")).status_code, 200)
        resp = self.client.post(reverse("qms:record_create", args=[wf.PROBLEM_REPORT]),
                                {"device": self.device.pk, "title": "ASR drops last word",
                                 "description": "Site S03"})
        self.assertRedirects(resp, reverse("qms:record_detail", args=["PR-0001"]))
        self.assertEqual(self.client.get(reverse("qms:record_detail",
                                                 args=["PR-0001"])).status_code, 200)
        self.client.post(reverse("qms:record_transition", args=["PR-0001", "triage"]))
        self.assertEqual(Record.objects.get(ref="PR-0001").status, "triage")
        self.assertEqual(self.client.get(reverse("qms:record_list")).status_code, 200)
        csv = self.client.get(reverse("qms:record_audit_export", args=["PR-0001"]))
        self.assertIn(b"transition", csv.content)

    def test_login_required(self):
        # The home page is the public landing page: no QMS data, no dashboard.
        resp = self.client.get(reverse("qms:dashboard"))
        self.assertTemplateUsed(resp, "qms/landing.html")
        self.assertTemplateNotUsed(resp, "qms/dashboard.html")
        resp = self.client.get(reverse("qms:record_list"))
        self.assertEqual(resp.status_code, 302)
