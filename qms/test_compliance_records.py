"""ISO 13485 records added for clauses 5.6, 7.3.3 to 7.3.5, 8.2.4, 8.3 and the retention rules
of 4.2.4 and 4.2.5."""
from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from . import workflow as wf
from .models import Device, DeviceMembership, Document, ImmutableError, Record
from .retention import add_years, retention_items, retention_until
from .services import TransitionError, obsolete_document, perform_transition

PW = "test-pass-123"


def make_user(username, role):
    user = User.objects.create_user(username, password=PW)
    user.groups.add(Group.objects.get_or_create(name=role)[0])
    return user


class Base(TestCase):
    def setUp(self):
        self.device = Device.objects.create(name="Test device", code="TST")
        self.eng = make_user("eng", wf.ENGINEER)
        self.qa = make_user("qa", wf.QA)
        self.qa2 = make_user("qa2", wf.QA)
        for u in User.objects.all():
            DeviceMembership.objects.create(device=self.device, user=u)

    def new(self, record_type, by=None, **fields):
        return Record.objects.create(device=self.device, record_type=record_type, title="Test",
                                     created_by=by or self.eng, **fields)

    def step(self, record, name, user, **kw):
        return perform_transition(record, name, user, password=PW, **kw)


class InternalAuditTests(Base):
    def test_lead_auditor_cannot_audit_their_own_area(self):
        ia = self.new(wf.INTERNAL_AUDIT, owner=self.qa, auditee=self.qa, audit_scope="7.4",
                      planned_date=date(2026, 1, 1))
        with self.assertRaisesMessage(TransitionError, "cannot be the auditee"):
            self.step(ia, "start", self.qa)

    def test_independent_auditor_runs_and_qa_closes(self):
        ia = self.new(wf.INTERNAL_AUDIT, owner=self.eng, auditee=self.qa2, audit_scope="7.4",
                      planned_date=date(2026, 1, 1))
        self.assertEqual(ia.ref, "IA-0001")
        self.assertEqual(ia.next_deadline, date(2026, 1, 1))
        self.step(ia, "start", self.eng)
        ia.refresh_from_db()
        ia.investigation_summary = "Two findings: checklist not kept"
        ia.save()
        self.step(ia, "report", self.eng)
        ia.refresh_from_db()
        ia.resolution = "Two findings, CAPA raised"
        ia.save()
        with self.assertRaisesMessage(TransitionError, "Requires role: QA"):
            self.step(ia, "close", self.eng)
        self.step(ia, "close", self.qa2)
        ia.refresh_from_db()
        self.assertEqual(ia.status, "closed")
        self.assertIsNone(ia.next_deadline)

    def test_closer_may_not_be_the_record_author(self):
        ia = self.new(wf.INTERNAL_AUDIT, by=self.qa, owner=self.eng, auditee=self.qa2,
                      audit_scope="7.4", planned_date=date(2026, 1, 1))
        self.step(ia, "start", self.eng)
        ia.refresh_from_db()
        ia.investigation_summary = "No findings"
        ia.save()
        self.step(ia, "report", self.eng)
        ia.refresh_from_db()
        ia.resolution = "Done"
        ia.save()
        with self.assertRaisesMessage(TransitionError, "independent sign-off"):
            self.step(ia, "close", self.qa)


class ManagementReviewTests(Base):
    def test_held_review_needs_inputs_and_closes_with_outputs(self):
        mr = self.new(wf.MANAGEMENT_REVIEW, planned_date=date(2026, 2, 1))
        self.assertEqual(mr.ref, "MR-0001")
        with self.assertRaises(TransitionError) as ctx:
            self.step(mr, "hold", self.qa)
        self.assertEqual(len(ctx.exception.errors), 2)  # attendees and review inputs
        mr.refresh_from_db()
        mr.attendees, mr.review_inputs = "QA lead, engineering lead", "Complaints, CAPA, audits"
        mr.save()
        self.step(mr, "hold", self.qa)
        mr.refresh_from_db()
        with self.assertRaises(TransitionError):  # no outputs yet
            self.step(mr, "close", self.qa)
        mr.resolution, mr.resource_needs = "Add a second assessor", "None"
        mr.save()
        with self.assertRaisesMessage(TransitionError, "Requires role: QA"):
            self.step(mr, "close", self.eng)
        self.step(mr, "close", self.qa)
        mr.refresh_from_db()
        self.assertEqual(mr.status, "closed")


class NonconformanceTests(Base):
    def setUp(self):
        super().setUp()
        self.nc = self.new(wf.NONCONFORMANCE, investigation_summary="Build 12 failed checksum")
        self.step(self.nc, "evaluate", self.eng)

    def test_disposition_needs_a_choice_and_qa_signature(self):
        self.nc.refresh_from_db()
        with self.assertRaises(TransitionError):
            self.step(self.nc, "decide", self.qa)
        self.nc.refresh_from_db()
        self.nc.nc_disposition = "scrap"
        self.nc.save()
        with self.assertRaisesMessage(TransitionError, "Requires role: QA"):
            self.step(self.nc, "decide", self.eng)
        self.step(self.nc, "decide", self.qa)
        self.nc.refresh_from_db()
        self.assertEqual(self.nc.status, "disposition")

    def test_concession_needs_justification_and_risk_file_checked(self):
        self.nc.refresh_from_db()
        self.nc.nc_disposition = "use_as_is_concession"
        self.nc.save()
        with self.assertRaisesMessage(TransitionError, "justification"):
            self.step(self.nc, "decide", self.qa)
        self.nc.refresh_from_db()
        self.nc.concession_justification = "Cosmetic only; no effect on dosing output"
        self.nc.risk_file_updated = "pending"
        self.nc.save()
        with self.assertRaisesMessage(TransitionError, "risk file"):
            self.step(self.nc, "decide", self.qa)
        self.nc.refresh_from_db()
        self.nc.risk_file_updated = "not_needed"
        self.nc.save()
        self.step(self.nc, "decide", self.qa)

    def test_disposition_is_verified_then_closed(self):
        self.nc.refresh_from_db()
        self.nc.nc_disposition = "rework"
        self.nc.save()
        self.step(self.nc, "decide", self.qa)
        with self.assertRaises(TransitionError):
            self.step(self.nc, "verify", self.eng)
        self.nc.refresh_from_db()
        self.nc.verification_evidence = "Re-test run 1042"
        self.nc.save()
        self.step(self.nc, "verify", self.eng)
        self.nc.refresh_from_db()
        self.nc.resolution = "Reworked and re-tested"
        self.nc.save()
        with self.assertRaisesMessage(TransitionError, "Requires role: QA"):
            self.step(self.nc, "close", self.eng)
        self.step(self.nc, "close", self.qa2)
        self.nc.refresh_from_db()
        self.assertEqual(self.nc.status, "closed")


class DesignControlTests(Base):
    def test_output_needs_acceptance_criteria(self):
        out = self.new(wf.DESIGN_CONTROL, design_element="output")
        with self.assertRaisesMessage(TransitionError, "Acceptance criteria"):
            self.step(out, "submit", self.eng)

    def test_review_needs_participants_and_date(self):
        review = self.new(wf.DESIGN_CONTROL, design_element="review",
                          acceptance_criteria="Output meets input DI-004")
        with self.assertRaisesMessage(TransitionError, "participants and review date"):
            self.step(review, "submit", self.eng)
        review.refresh_from_db()
        review.attendees, review.planned_date = "QA, firmware lead", date(2026, 3, 1)
        review.save()
        self.step(review, "submit", self.eng)
        review.refresh_from_db()
        review.investigation_summary = "Design meets inputs"
        review.save()
        self.step(review, "approve", self.qa)
        review.refresh_from_db()
        self.assertEqual(review.status, "closed")  # approved design is locked
        with self.assertRaises(ImmutableError):
            review.investigation_summary = "changed"
            review.save()

    def test_approval_is_independent(self):
        inp = self.new(wf.DESIGN_CONTROL, by=self.qa, design_element="input",
                       acceptance_criteria="Reads a 10-bit sensor")
        self.step(inp, "submit", self.qa)
        inp.refresh_from_db()
        inp.investigation_summary = "Adequate"
        inp.save()
        with self.assertRaisesMessage(TransitionError, "independent sign-off"):
            self.step(inp, "approve", self.qa)


class RetentionTests(Base):
    def test_add_years_handles_leap_day(self):
        self.assertEqual(add_years(date(2024, 2, 29), 1), date(2025, 3, 1))
        self.assertEqual(add_years(date(2026, 5, 1), 2), date(2028, 5, 1))

    @override_settings(QMS_RETENTION_MIN_YEARS=2)
    def test_minimum_is_two_years_without_lifetime(self):
        self.assertEqual(retention_until(self.device, date(2026, 1, 1)), date(2028, 1, 1))

    @override_settings(QMS_RETENTION_MIN_YEARS=2)
    def test_expected_lifetime_extends_retention(self):
        self.device.expected_lifetime_years = 15
        self.device.save()
        self.assertEqual(retention_until(self.device, date(2026, 1, 1)), date(2041, 1, 1))

    def test_closed_record_and_withdrawn_document_are_listed(self):
        cr = self.new(wf.CHANGE_REQUEST)
        Record.objects.filter(pk=cr.pk).update(status="closed", closed_at="2026-01-10T09:00:00Z")
        doc = Document.objects.create(title="Retained SOP", doc_type="SOP", device=self.device)
        obsolete_document(doc, self.qa, PW, "Superseded by process change")
        doc.refresh_from_db()
        self.assertEqual(doc.obsolete_on, date.today())

        rows = retention_items()
        kinds = {r["kind"] for r in rows}
        self.assertEqual(kinds, {"Record", "Document"})
        self.assertFalse(any(r["lifetime_defined"] for r in rows))

        soon = retention_items(within_days=3650)
        self.assertEqual(len(soon), 2)
        self.assertEqual(retention_items(within_days=-1), [])

    def test_report_command_prints_items_and_flags_missing_lifetime(self):
        cr = self.new(wf.CHANGE_REQUEST)
        Record.objects.filter(pk=cr.pk).update(status="closed", closed_at="2026-01-10T09:00:00Z")
        out = StringIO()
        call_command("retention_report", stdout=out)
        text = out.getvalue()
        self.assertIn(cr.ref, text)
        self.assertIn("Set the device's expected lifetime", text)
        out = StringIO()
        call_command("retention_report", "--within-days", "-1", stdout=out)
        self.assertIn("No items in scope.", out.getvalue())


class RecordPrefixTests(Base):
    def test_new_types_have_prefixes_and_fields(self):
        for t in [wf.INTERNAL_AUDIT, wf.MANAGEMENT_REVIEW, wf.NONCONFORMANCE, wf.DESIGN_CONTROL]:
            self.assertIn(t, wf.REF_PREFIX)
            self.assertIn(t, wf.TYPE_FIELDS)
            self.assertIn(t, wf.WORKFLOWS)
            self.assertNotIn("pending", [v for v, _ in wf.NC_DISPOSITIONS])


class RejectionTests(Base):
    def test_nonconformance_can_be_rejected_with_a_reason(self):
        nc = self.new(wf.NONCONFORMANCE, investigation_summary="Reported in error")
        self.step(nc, "evaluate", self.eng)
        with self.assertRaisesMessage(TransitionError, "comment"):
            self.step(nc, "reject", self.qa)
        self.step(nc, "reject", self.qa, comment="Not a nonconformity: spec was misread")
        nc.refresh_from_db()
        self.assertEqual(nc.status, "rejected")
        self.assertTrue(nc.is_locked)

    def test_design_review_can_be_rejected_with_a_reason(self):
        des = self.new(wf.DESIGN_CONTROL, design_element="input",
                       acceptance_criteria="Reads a 10-bit sensor")
        self.step(des, "submit", self.eng)
        with self.assertRaisesMessage(TransitionError, "comment"):
            self.step(des, "reject", self.qa)
        self.step(des, "reject", self.qa, comment="Criteria are not measurable")
        des.refresh_from_db()
        self.assertEqual(des.status, "rejected")


class RetentionOfQmsWideDocumentTests(Base):
    @override_settings(QMS_RETENTION_MIN_YEARS=2)
    def test_qms_wide_document_uses_the_longest_device_lifetime(self):
        self.device.expected_lifetime_years = 12
        self.device.save()
        doc = Document.objects.create(title="QMS-wide SOP", doc_type="SOP", device=None)
        obsolete_document(doc, self.qa, PW, "Replaced by a new procedure")
        doc.refresh_from_db()
        rows = [r for r in retention_items() if r["kind"] == "Document"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["until"], add_years(doc.obsolete_on, 12))
        self.assertTrue(rows[0]["lifetime_defined"])


class WebUITests(Base):
    """The four new record types can be created, moved on and viewed in the browser."""

    def test_each_new_type_is_created_and_detail_renders(self):
        self.client.login(username="eng", password=PW)
        cases = {
            wf.INTERNAL_AUDIT: {"title": "Supplier audit", "audit_scope": "7.4 purchasing",
                                "auditee": self.qa2.pk, "owner": self.eng.pk,
                                "planned_date": "2026-06-01"},
            wf.MANAGEMENT_REVIEW: {"title": "Q2 review", "planned_date": "2026-07-01"},
            wf.NONCONFORMANCE: {"title": "Checksum mismatch", "software_version": "2.3.1"},
            wf.DESIGN_CONTROL: {"title": "Sensor input", "design_element": "input",
                                "acceptance_criteria": "Reads a 10-bit sensor"},
        }
        for record_type, fields in cases.items():
            with self.subTest(record_type=record_type):
                data = {"device": self.device.pk, "description": "", **fields}
                resp = self.client.post(reverse("qms:record_create", args=[record_type]), data)
                record = Record.objects.filter(record_type=record_type).latest("pk")
                self.assertRedirects(resp, reverse("qms:record_detail", args=[record.ref]))
                self.assertEqual(self.client.get(
                    reverse("qms:record_detail", args=[record.ref])).status_code, 200)

    def test_transition_is_refused_in_the_browser_without_required_fields(self):
        self.client.login(username="eng", password=PW)
        self.client.post(reverse("qms:record_create", args=[wf.NONCONFORMANCE]),
                         {"device": self.device.pk, "title": "Checksum mismatch"})
        self.client.post(reverse("qms:record_transition", args=["NC-0001", "evaluate"]))
        self.assertEqual(Record.objects.get(ref="NC-0001").status, "evaluation")
        self.client.post(reverse("qms:record_transition", args=["NC-0001", "reject"]))
        self.assertEqual(Record.objects.get(ref="NC-0001").status, "evaluation")

    def test_device_form_offers_expected_lifetime(self):
        from .forms import DeviceForm
        self.assertIn("expected_lifetime_years", DeviceForm().fields)
