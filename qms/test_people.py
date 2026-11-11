"""The People page: who is on each device's team, and changing roles, removing and adding people
from it. Every change is audited."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from . import workflow as wf
from .models import AuditEvent, Device, DeviceMembership

PW = "test-pass-123"


def user(name, *roles):
    u = User.objects.create_user(name, email=f"{name}@example.org", password=PW)
    for r in roles:
        u.groups.add(Group.objects.get_or_create(name=r)[0])
    return u


class PeopleTests(TestCase):
    def setUp(self):
        self.a = Device.objects.create(name="Device A", code="DA")
        self.b = Device.objects.create(name="Device B", code="DB")
        self.eng_a = user("eng_a", wf.ENGINEER)
        self.qa_a = user("qa_a", wf.QA)
        self.eng_b = user("eng_b", wf.ENGINEER)
        self.newbie = user("newbie")  # has an account, not on any team yet
        self.head = user("head", wf.QA, wf.ALL_DEVICES)  # sees everything
        self.m_eng_a = DeviceMembership.objects.create(device=self.a, user=self.eng_a, roles=wf.ENGINEER)
        self.m_qa_a = DeviceMembership.objects.create(device=self.a, user=self.qa_a, roles=wf.QA)
        self.m_eng_b = DeviceMembership.objects.create(device=self.b, user=self.eng_b, roles=wf.ENGINEER)

    def login(self, u):
        self.client.force_login(u)

    def audit_count(self, device):
        return AuditEvent.objects.filter(object_type="Device Membership",
                                         object_ref__endswith=f"@ {device.code}").count()

    def test_lists_only_people_on_visible_devices(self):
        self.login(self.eng_a)
        resp = self.client.get(reverse("qms:people"))
        self.assertEqual(resp.status_code, 200)
        listed = {(r["user"].username, m["m"].device.code)
                  for r in resp.context["people"] for m in r["memberships"]}
        self.assertEqual(listed, {("eng_a", "DA"), ("qa_a", "DA")})

    def test_people_without_manage_rights_see_no_edit_controls(self):
        self.login(self.eng_a)
        resp = self.client.get(reverse("qms:people"))
        self.assertEqual(resp.context["add_forms"], [])
        self.assertNotContains(resp, "Save roles")
        self.assertNotContains(resp, "Remove from team")

    def test_manager_sees_controls_but_not_for_own_row(self):
        self.login(self.qa_a)
        resp = self.client.get(reverse("qms:people"))
        rows = {r["user"].username: r["memberships"][0] for r in resp.context["people"]}
        self.assertTrue(rows["eng_a"]["manage"])
        self.assertFalse(rows["qa_a"]["manage"])
        self.assertEqual([f["device"].code for f in resp.context["add_forms"]], ["DA"])

    def test_manager_changes_roles_and_it_is_audited(self):
        self.login(self.qa_a)
        before = self.audit_count(self.a)
        resp = self.client.post(reverse("qms:team_roles", args=[self.m_eng_a.pk]), {
            f"m{self.m_eng_a.pk}-roles": [wf.ENGINEER, wf.QA],
            f"m{self.m_eng_a.pk}-note": "Lead developer",
            "next": reverse("qms:people"),
        })
        self.assertRedirects(resp, reverse("qms:people"))
        self.m_eng_a.refresh_from_db()
        self.assertEqual(set(self.m_eng_a.role_list()), {wf.ENGINEER, wf.QA})
        self.assertEqual(self.m_eng_a.note, "Lead developer")
        self.assertGreater(self.audit_count(self.a), before)

    def test_manager_removes_person_and_it_is_audited(self):
        self.login(self.qa_a)
        before = self.audit_count(self.a)
        resp = self.client.post(reverse("qms:team_remove", args=[self.m_eng_a.pk]),
                                {"next": reverse("qms:people")})
        self.assertRedirects(resp, reverse("qms:people"))
        self.m_eng_a.refresh_from_db()
        self.assertFalse(self.m_eng_a.active)
        self.assertGreater(self.audit_count(self.a), before)

    def test_manager_adds_existing_account_and_it_is_audited(self):
        self.login(self.qa_a)
        before = self.audit_count(self.a)
        resp = self.client.post(reverse("qms:team_add", args=["DA"]), {
            "user": self.newbie.pk, "roles": [wf.ENGINEER], "note": "Tester",
            "next": reverse("qms:people"),
        })
        self.assertRedirects(resp, reverse("qms:people"))
        m = DeviceMembership.objects.get(device=self.a, user=self.newbie)
        self.assertTrue(m.active)
        self.assertEqual(m.role_list(), [wf.ENGINEER])
        self.assertGreater(self.audit_count(self.a), before)

    def test_manager_cannot_change_roles_on_another_device(self):
        self.login(self.qa_a)
        self.client.post(reverse("qms:team_roles", args=[self.m_eng_b.pk]),
                         {f"m{self.m_eng_b.pk}-roles": [wf.QA]})
        self.m_eng_b.refresh_from_db()
        self.assertEqual(self.m_eng_b.role_list(), [wf.ENGINEER])

    def test_return_address_must_be_on_this_site(self):
        self.login(self.qa_a)
        resp = self.client.post(reverse("qms:team_remove", args=[self.m_eng_a.pk]),
                                {"next": "https://evil.example/steal"})
        self.assertRedirects(resp, reverse("qms:device_detail", args=["DA"]),
                             fetch_redirect_response=False)

    def test_organisation_wide_roles_are_listed_read_only(self):
        self.login(self.eng_a)
        resp = self.client.get(reverse("qms:people"))
        self.assertIn(self.head, [p["user"] for p in resp.context["org_people"]])
