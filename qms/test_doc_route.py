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
        self.assertEqual([s["number"] for s in route], [1, 2, 3, 4, 5, 6])
        self.assertEqual(doc_route.current_stage(route)["number"], 1)
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
