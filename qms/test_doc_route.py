"""Tests for the documentation route panel on the device page."""
from django.urls import reverse

from . import doc_route, techfile
from .models import Device, Hazard, RiskControl
from .test_devices import PW, Base


def route_for(device):
    data = techfile.gather(device)
    return doc_route.stages(device, data, techfile.completeness_checks(device, data))


def item(stage_list, number, label_start):
    stage = stage_list[number - 1]
    return next(i for i in stage["items"] if i["label"].startswith(label_start))


class DocumentationRouteTests(Base):
    def test_new_device_starts_at_stage_one_with_nothing_done_beyond_its_record(self):
        d = Device.objects.create(name="Blank", code="BLK")
        route = route_for(d)
        self.assertEqual([s["number"] for s in route], ["1", "2", "3", "4", "5", "6"])
        self.assertEqual(doc_route.current_stage(route)["number"], "1")
        self.assertFalse(item(route, 2, "Classified")["done"])
        self.assertFalse(item(route, 4, "Risk register")["done"])
        self.assertEqual(route[3]["status"], "todo")

    def test_checks_follow_the_device_record(self):
        route = route_for(self.dev)
        stage2 = route[1]
        # complete_device() fills every stage-2 field.
        self.assertEqual(stage2["status"], "done")
        self.assertTrue(stage2["gate_passed"])
        self.dev.uk_classification = "tbd"
        self.dev.save()
        route = route_for(self.dev)
        self.assertFalse(item(route, 2, "Classified")["done"])
        self.assertFalse(route[1]["gate_passed"])
        self.assertEqual(route[1]["status"], "progress")

    def test_risk_gate_needs_a_control_on_every_hazard(self):
        h = Hazard(device=self.dev, title="False negative", hazard="Missed decline",
                   harm="Delayed diagnosis", severity_initial=2, probability_initial=2)
        h.save()
        route = route_for(self.dev)
        self.assertTrue(item(route, 4, "Risk register")["done"])
        self.assertFalse(item(route, 4, "Every hazard has a risk control")["done"])
        self.assertFalse(route[3]["gate_passed"])
        c = RiskControl.objects.create(hazard=h, description="Second reader",
                                      control_type="design", verified=False)
        route = route_for(self.dev)
        self.assertTrue(route[3]["gate_passed"])
        self.assertFalse(item(route, 4, "Every risk control verified")["done"])
        c.verified, c.verification_evidence = True, "TR-12 second-reader test"
        c.save()
        self.assertTrue(item(route_for(self.dev), 4, "Every risk control verified")["done"])

    def test_evidence_documents_complete_stage_five(self):
        self.assertFalse(route_for(self.dev)[4]["gate_passed"])
        self.effective_doc("V&V report", "verification")
        self.effective_doc("Clinical evaluation", "clinical")
        stage5 = route_for(self.dev)[4]
        self.assertTrue(stage5["gate_passed"])
        self.assertEqual(stage5["status"], "done")

    def test_overall_is_the_share_of_checks_that_pass(self):
        route = route_for(self.dev)
        done = sum(s["done"] for s in route)
        total = sum(s["total"] for s in route)
        self.assertEqual(doc_route.overall(route), round(100 * done / total))

    def test_device_page_shows_the_route_with_links_to_fix_open_checks(self):
        self.client.login(username="eng", password=PW)
        resp = self.client.get(reverse("qms:device_detail", args=[self.dev.code]))
        self.assertContains(resp, 'id="documentation-route"')
        self.assertContains(resp, "Hazards, controls and residual risk")
        self.assertContains(resp, f'href="{reverse("qms:hazard_list")}"')
        self.assertEqual(len(resp.context["route"]), 6)
        # Two-column layout that stacks on narrow screens, not a fixed inline grid.
        self.assertContains(resp, '<div class="grid split">')
        self.assertNotContains(resp, "minmax(300px,1fr)")
        # Inline help on the panel heading and on each gate line.
        self.assertContains(resp, 'aria-label="Help: Documentation route"')
        self.assertContains(resp, 'aria-label="Help: Gate"')


class RouteFollowsDeviceTests(Base):
    """The panel follows the device's route and shows each approver gate's sign-off."""

    def test_retrofit_device_shows_steps_a_to_g(self):
        self.dev.development_route = "retrofit"
        self.dev.save()
        route = route_for(self.dev)
        self.assertEqual([s["number"] for s in route], list("ABCDEFG"))
        self.assertEqual([s["number"] for s in route if s["signoff"]], list("ABCDEFG"))
        self.assertEqual(route[4]["signoff"]["approver_role"], "Clinical Safety Officer")

    def test_gap_assessment_is_an_effective_device_document_with_that_title(self):
        self.dev.development_route = "retrofit"
        self.dev.save()
        self.assertFalse(route_for(self.dev)[0]["gate_passed"])
        self.effective_doc("SkinCheck gap assessment", "")
        step_a = route_for(self.dev)[0]
        self.assertTrue(step_a["gate_passed"])
        self.assertEqual(step_a["signoff"]["state"], "ready")

    def test_greenfield_gates_sit_on_stages_2_4_5_and_6(self):
        route = route_for(self.dev)
        self.assertEqual([s["number"] for s in route if s["signoff"]], ["2", "4", "5", "6"])

    def test_signoff_states_follow_checks_and_approval(self):
        from . import tasks
        route = route_for(self.dev)
        self.assertEqual(route[1]["signoff"]["state"], "ready")  # stage 2 checks pass
        self.assertEqual(route[4]["signoff"]["state"], "blocked")  # no evidence documents
        gate = tasks.ensure_gates(self.dev)[0]
        tasks.approve_gate(gate, self.qa, PW)
        route = route_for(self.dev)
        self.assertEqual(route[1]["signoff"]["state"], "approved")
        self.assertEqual(route[1]["signoff"]["approved_by"], self.qa)
        self.dev.classification_rule = ""
        self.dev.save()
        self.assertEqual(route_for(self.dev)[1]["signoff"]["state"], "stale")

    def test_device_page_draws_the_route_diagram(self):
        self.client.login(username="eng", password=PW)
        resp = self.client.get(reverse("qms:device_detail", args=[self.dev.code]))
        self.assertContains(resp, "Documentation route · Greenfield")
        self.assertContains(resp, 'class="route-flow"')
        self.assertContains(resp, 'href="#route-stage-4"')
        self.assertContains(resp, 'class="route-gate ready"')
        self.assertContains(resp, f'href="{reverse("qms:device_tasks", args=[self.dev.code])}"')

    def test_failing_gate_checks_stop_signing_and_alert_the_approver(self):
        from . import tasks
        from .services import TransitionError
        self.dev.classification_rule = ""
        self.dev.save()
        self.client.login(username="qa", password=PW)
        resp = self.client.get(reverse("qms:device_tasks", args=[self.dev.code]))
        self.assertContains(resp, "Can't be signed yet: gate checks not passing")
        self.assertContains(resp, "Classification rationale recorded")
        self.assertNotContains(resp, "Sign and approve this gate")
        gate = tasks.ensure_gates(self.dev)[0]
        with self.assertRaises(TransitionError) as caught:
            tasks.approve_gate(gate, self.qa, PW)
        self.assertIn("Classification rationale recorded", str(caught.exception))
        gate.refresh_from_db()
        self.assertEqual(gate.status, "open")
        # Posting the form directly is refused too.
        self.client.post(reverse("qms:gate_approve", args=[gate.pk]), {"password": PW})
        gate.refresh_from_db()
        self.assertEqual(gate.status, "open")

    def test_once_checks_pass_the_approver_can_sign(self):
        from . import tasks
        self.client.login(username="qa", password=PW)
        resp = self.client.get(reverse("qms:device_tasks", args=[self.dev.code]))
        self.assertContains(resp, "Gate checks pass")
        self.assertContains(resp, "Sign and approve this gate")
        gate = tasks.ensure_gates(self.dev)[0]
        tasks.approve_gate(gate, self.qa, PW)
        gate.refresh_from_db()
        self.assertEqual(gate.status, "approved")

    def test_gate_open_email_alerts_the_approver_to_failing_checks(self):
        from django.core import mail
        from . import notifications, tasks
        self.dev.classification_rule = ""
        self.dev.save()
        gate = tasks.ensure_gates(self.dev)[0]
        mail.outbox.clear()
        with self.settings(QMS_NOTIFICATIONS_ENABLED=True), \
                self.captureOnCommitCallbacks(execute=True):
            notifications.gate_open(gate)
        self.assertTrue(mail.outbox)
        self.assertIn("gate checks not passing", mail.outbox[0].subject)
        self.assertIn("- Classification rationale recorded", mail.outbox[0].body)
