"""Device teams: isolation between teams, people on several teams, and All-device access."""
import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import services, techfile
from . import workflow as wf
from .access import accessible_devices, can_access
from .models import (AuditEvent, Device, DeviceMembership, Document, Hazard, Record,
                     TrainingAssignment, TrainingRequirement)
from .services import TransitionError

PW = "test-pass-123"
MEDIA = tempfile.mkdtemp(prefix="qms-test-teams-")


def user(name, *roles):
    u = User.objects.create_user(name, email=f"{name}@example.org", password=PW)
    for r in roles:
        u.groups.add(Group.objects.get_or_create(name=r)[0])
    return u


@override_settings(MEDIA_ROOT=MEDIA)
class TeamTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.a = Device.objects.create(name="Device A", code="DA")
        self.b = Device.objects.create(name="Device B", code="DB")
        self.eng_a, self.qa_a = user("eng_a", wf.ENGINEER), user("qa_a", wf.QA)
        self.qa_a2 = user("qa_a2", wf.QA)
        self.eng_b, self.qa_b = user("eng_b", wf.ENGINEER), user("qa_b", wf.QA)
        self.both = user("both", wf.ENGINEER)                      # on two teams
        self.head = user("head", wf.QA, wf.ALL_DEVICES)            # sees everything
        for u in (self.eng_a, self.qa_a, self.qa_a2, self.both):
            DeviceMembership.objects.create(device=self.a, user=u)
        for u in (self.eng_b, self.qa_b, self.both):
            DeviceMembership.objects.create(device=self.b, user=u)
        self.rec_a = Record.objects.create(device=self.a, record_type=wf.PROBLEM_REPORT,
                                           title="Alpha bug", created_by=self.eng_a)
        self.rec_b = Record.objects.create(device=self.b, record_type=wf.PROBLEM_REPORT,
                                           title="Bravo bug", created_by=self.eng_b)

    def login(self, u):
        self.client.force_login(u)

    # --- who can see what ------------------------------------------------------------

    def test_accessible_devices(self):
        self.assertEqual(set(accessible_devices(self.eng_a)), {self.a})
        self.assertEqual(set(accessible_devices(self.both)), {self.a, self.b})
        self.assertEqual(set(accessible_devices(self.head)), {self.a, self.b})
        self.assertTrue(can_access(self.eng_a, None))  # QMS-wide is visible to all

    def test_other_teams_records_are_invisible(self):
        self.login(self.eng_a)
        lst = self.client.get(reverse("qms:record_list"))
        self.assertContains(lst, "Alpha bug")
        self.assertNotContains(lst, "Bravo bug")
        self.assertEqual(self.client.get(reverse("qms:record_detail",
                                                 args=[self.rec_b.ref])).status_code, 404)
        self.assertEqual(self.client.get(reverse("qms:device_detail",
                                                 args=["DB"])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("qms:device_list")), "Device B")
        self.assertNotContains(self.client.get(reverse("qms:dashboard")), "Bravo bug")

    def test_switcher_only_offers_own_devices(self):
        self.login(self.eng_a)
        self.client.post(reverse("qms:set_device"), {"device": self.b.pk})
        self.assertEqual(self.client.session.get("qms_device_id"), None)
        self.login(self.both)
        self.client.post(reverse("qms:set_device"), {"device": self.b.pk})
        lst = self.client.get(reverse("qms:record_list"))
        self.assertContains(lst, "Bravo bug")
        self.assertNotContains(lst, "Alpha bug")

    def test_multi_team_member_and_head_see_both(self):
        for u in (self.both, self.head):
            self.login(u)
            lst = self.client.get(reverse("qms:record_list"))
            self.assertContains(lst, "Alpha bug")
            self.assertContains(lst, "Bravo bug")

    def test_full_audit_trail_needs_all_device_access(self):
        self.login(self.qa_a)
        self.assertEqual(self.client.get(reverse("qms:audit_log")).status_code, 302)
        self.assertEqual(self.client.get(reverse("qms:audit_export")).status_code, 404)
        self.assertEqual(self.client.get(
            reverse("qms:record_audit_export", args=[self.rec_a.ref])).status_code, 200)
        self.login(self.head)
        self.assertEqual(self.client.get(reverse("qms:audit_log")).status_code, 200)

    def test_documents(self):
        shared = Document.objects.create(title="Shared SOP", doc_type="SOP")
        private = Document.objects.create(title="B plan", doc_type="PLAN", device=self.b)
        self.login(self.eng_a)
        lst = self.client.get(reverse("qms:document_list"))
        self.assertContains(lst, "Shared SOP")
        self.assertNotContains(lst, "B plan")
        self.assertEqual(self.client.get(reverse("qms:document_detail",
                                                 args=[private.number])).status_code, 404)
        self.assertEqual(self.client.get(reverse("qms:document_detail",
                                                 args=[shared.number])).status_code, 200)

    # --- what they can do -----------------------------------------------------------

    def test_services_refuse_other_teams_even_when_called_directly(self):
        with self.assertRaisesMessage(TransitionError, "team"):
            services.perform_transition(self.rec_b, "triage", self.qa_a)
        h = Hazard.objects.create(device=self.b, title="h", hazard="h", harm="h",
                                  severity_initial=1, probability_initial=1)
        with self.assertRaisesMessage(TransitionError, "team"):
            services.accept_hazard(h, self.qa_a, PW)
        with self.assertRaisesMessage(TransitionError, "team"):
            techfile.generate_technical_file(self.b, self.qa_a)
        doc = Document.objects.create(title="B plan", doc_type="PLAN", device=self.b)
        with self.assertRaisesMessage(TransitionError, "team"):
            services.create_version(doc, self.eng_a, version="1.0", change_summary="x")
        # the multi-team member can act on both
        services.perform_transition(self.rec_a, "triage", self.both)
        services.perform_transition(self.rec_b, "triage", self.both)

    def test_forms_refuse_other_teams_devices_hazards_and_links(self):
        hb = Hazard.objects.create(device=self.b, title="hb", hazard="h", harm="h",
                                   severity_initial=1, probability_initial=1)
        ha = Hazard.objects.create(device=self.a, title="ha", hazard="h", harm="h",
                                   severity_initial=1, probability_initial=1)
        self.login(self.eng_a)
        url = reverse("qms:record_create", args=[wf.PROBLEM_REPORT])
        self.client.post(url, {"device": self.b.pk, "title": "sneaky"})
        self.assertFalse(Record.objects.filter(title="sneaky").exists())
        self.client.post(url, {"device": self.a.pk, "title": "mixed", "hazards": [hb.pk]})
        self.assertFalse(Record.objects.filter(title="mixed").exists())
        self.client.post(url, {"device": self.a.pk, "title": "fine", "hazards": [ha.pk]})
        self.assertTrue(Record.objects.filter(title="fine").exists())

        self.client.post(reverse("qms:record_link", args=[self.rec_a.ref]),
                         {"link_type": "relates_to", "target_ref": self.rec_b.ref})
        self.assertFalse(self.rec_a.outgoing_links.exists())

        # a person on both teams still can't attach device B's hazard to device A's record
        self.login(self.both)
        self.client.post(url, {"device": self.a.pk, "title": "mixed2", "hazards": [hb.pk]})
        self.assertFalse(Record.objects.filter(title="mixed2").exists())

    def test_notifications_go_only_to_the_team(self):
        with self.captureOnCommitCallbacks(execute=True):
            Record.objects.create(device=self.b, record_type=wf.INCIDENT, title="B incident")
        recipients = {addr for m in mail.outbox for addr in m.to}
        self.assertIn(self.qa_b.email, recipients)
        self.assertIn(self.head.email, recipients)
        self.assertNotIn(self.qa_a.email, recipients)
        self.assertIn("[SAMD_QMS] URGENT: new DB incident", mail.outbox[0].subject)

    def test_training_for_device_documents_goes_to_the_team(self):
        doc = Document.objects.create(title="A work instruction", doc_type="WI", device=self.a)
        TrainingRequirement.objects.create(document=doc, group=Group.objects.get(name=wf.ENGINEER))
        v = services.create_version(doc, self.eng_a, version="1.0", change_summary="x",
                                    file=SimpleUploadedFile("wi.pdf", b"%PDF wi"))
        services.submit_version(v, self.eng_a)
        services.approve_version(v, self.qa_a, PW)
        services.make_effective(v, self.qa_a)
        trainees = set(TrainingAssignment.objects.filter(version=v).values_list(
            "user__username", flat=True))
        self.assertEqual(trainees, {"eng_a", "both"})

    # --- managing teams ---------------------------------------------------------------

    def test_qa_on_team_manages_it_and_changes_are_audited(self):
        self.login(self.eng_a)
        self.client.post(reverse("qms:team_add", args=["DA"]),
                         {"user": self.eng_b.pk, "roles": [wf.ENGINEER]})
        self.assertFalse(can_access(self.eng_b, self.a))           # engineers can't

        self.login(self.qa_b)                                      # QA, but not on A
        self.assertEqual(self.client.post(reverse("qms:team_add", args=["DA"]),
                                          {"user": self.eng_b.pk, "roles": [wf.ENGINEER]})
                         .status_code, 404)

        self.login(self.qa_a)
        self.client.post(reverse("qms:team_add", args=["DA"]),
                         {"user": self.eng_b.pk, "roles": [wf.ENGINEER], "note": "Support"})
        self.assertTrue(can_access(self.eng_b, self.a))
        m = DeviceMembership.objects.get(device=self.a, user=self.eng_b)
        self.client.post(reverse("qms:team_remove", args=[m.pk]))
        m.refresh_from_db()
        self.assertFalse(m.active)
        self.assertFalse(can_access(self.eng_b, self.a))
        events = AuditEvent.for_object(m)
        self.assertEqual([e.action for e in events], ["create", "update"])
        with self.assertRaises(Exception):
            m.delete()

    def test_last_member_cannot_be_removed(self):
        solo = Device.objects.create(name="Solo", code="SO")
        m = DeviceMembership.objects.create(device=solo, user=self.qa_a)
        self.login(self.head)
        self.client.post(reverse("qms:team_remove", args=[m.pk]))
        m.refresh_from_db()
        self.assertTrue(m.active)

    def test_device_creator_joins_team(self):
        self.login(self.qa_a)
        self.client.post(reverse("qms:device_create"), {
            "name": "New", "code": "nw", "classification": "tbd",
            "regulatory_status": "development", "active": "on"})
        self.assertTrue(can_access(self.qa_a, Device.objects.get(code="NW")))
        self.assertFalse(can_access(self.eng_a, Device.objects.get(code="NW")))
