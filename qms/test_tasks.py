"""Tests for the per-device task board (kanban) and its page."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from . import tasks
from . import workflow as wf
from .models import Device, DeviceMembership, Record

PW = "test-pass-123"


def person(username, device, roles=""):
    user = User.objects.create_user(username, email=f"{username}@example.org", password=PW)
    if device is not None:
        DeviceMembership.objects.create(device=device, user=user, roles=roles)
    return user


class TaskBoardTests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(name="SkinCheck", code="SKN")
        self.engineer = person("eng", self.device, "Engineer")
        self.qa = person("qa", self.device, "QA")
        # A problem report that is released: closing it needs QA.
        self.record = Record.objects.create(
            device=self.device, record_type=wf.PROBLEM_REPORT, title="Threshold bug",
            owner=self.engineer)
        Record.objects.filter(pk=self.record.pk).update(status="released")
        self.record.refresh_from_db()

    def test_qa_sees_the_closing_step_to_do(self):
        board = tasks.board(self.qa, self.device)
        titles = [t.title for t in board["todo"]]
        details = [t.detail for t in board["todo"]]
        self.assertTrue(any("Threshold bug" in t for t in titles))
        self.assertTrue(any("Close" in d for d in details))

    def test_engineer_owner_sees_it_waiting_on_qa(self):
        board = tasks.board(self.engineer, self.device)
        self.assertEqual(board["todo"], [])
        self.assertEqual(len(board["waiting"]), 1)
        self.assertIn("Waiting for QA", board["waiting"][0].detail)

    def test_nobody_without_a_role_on_the_device_gets_a_board(self):
        outsider = person("out", None)
        self.assertEqual(tasks.board(outsider, self.device),
                         {"todo": [], "waiting": [], "done": []})

    def test_closed_records_drop_off_the_board(self):
        Record.objects.filter(pk=self.record.pk).update(status="closed")
        board = tasks.board(self.qa, self.device)
        self.assertFalse(any("Threshold bug" in t.title for t in board["todo"]))

    def test_page_shows_the_board_to_a_member(self):
        self.client.force_login(self.qa)
        response = self.client.get(reverse("qms:device_tasks", args=[self.device.code]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Threshold bug")
        self.assertContains(response, "To do")

    def test_page_refuses_someone_with_no_role_on_the_device(self):
        outsider = person("out2", None)
        self.client.force_login(outsider)
        response = self.client.get(reverse("qms:device_tasks", args=[self.device.code]))
        self.assertIn(response.status_code, (302, 403))
        self.assertNotContains(response, "Threshold bug", status_code=response.status_code)


class StageGateTests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(name="SkinCheck", code="SKN")
        self.qa = person("qa2", self.device, "QA")
        self.cso = person("cso", self.device, "Clinical Safety Officer")
        self.engineer = person("eng2", self.device, "Engineer")

    def test_gates_are_created_for_the_device_route(self):
        gates = tasks.ensure_gates(self.device)
        self.assertEqual([g.stage for g in gates], ["2", "4", "5", "6"])
        self.assertEqual(len(tasks.ensure_gates(self.device)), 4)  # idempotent

    def test_only_the_approver_role_can_approve_a_gate(self):
        from .services import TransitionError
        stage2 = tasks.ensure_gates(self.device)[0]  # stage 2 needs QA
        with self.assertRaises(TransitionError):
            tasks.approve_gate(stage2, self.cso, PW)
        with self.assertRaises(TransitionError):
            tasks.approve_gate(stage2, self.qa, "wrong-password")
        tasks.approve_gate(stage2, self.qa, PW)
        stage2.refresh_from_db()
        self.assertEqual(stage2.status, "approved")
        self.assertEqual(stage2.approved_by, self.qa)

    def test_gates_open_in_stage_order(self):
        from .services import TransitionError
        gates = tasks.ensure_gates(self.device)
        with self.assertRaises(TransitionError):  # stage 4 waits for stage 2
            tasks.approve_gate(gates[1], self.cso, PW)
        tasks.approve_gate(gates[0], self.qa, PW)
        tasks.approve_gate(gates[1], self.cso, PW)
        gates[1].refresh_from_db()
        self.assertEqual(gates[1].status, "approved")

    def test_approval_is_signed(self):
        from .models import Signature
        gate = tasks.ensure_gates(self.device)[0]
        tasks.approve_gate(gate, self.qa, PW)
        sig = Signature.objects.get(object_type="Stage Gate")
        self.assertEqual(sig.signer, self.qa)
        self.assertEqual(sig.transition, "approve_gate")

    def test_approval_tells_the_next_approver(self):
        from django.core import mail
        gates = tasks.ensure_gates(self.device)
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            tasks.approve_gate(gates[0], self.qa, PW)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.cso.email, mail.outbox[0].to)
        self.assertIn("Stage 4", mail.outbox[0].subject)

    def test_open_gate_is_to_do_for_its_approver_only(self):
        gates = tasks.ensure_gates(self.device)
        self.assertFalse(any("Stage 4" in t.title
                             for t in tasks.board(self.cso, self.device)["todo"]))
        tasks.approve_gate(gates[0], self.qa, PW)
        self.assertTrue(any("Stage 4" in t.title for t in tasks.board(self.cso, self.device)["todo"]))
        self.assertFalse(any("Stage 4" in t.title
                             for t in tasks.board(self.engineer, self.device)["todo"]))

    def test_gate_lanes_say_who_can_approve_now(self):
        gates = tasks.ensure_gates(self.device)
        lanes = tasks.gate_lanes(self.qa, self.device, gates)
        by_stage = {l["gate"].stage: l["can_approve"] for l in lanes}
        self.assertTrue(by_stage["2"])
        self.assertFalse(by_stage["4"])
