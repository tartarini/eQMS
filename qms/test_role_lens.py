"""Acting as one role: the choice narrows what a person can do and never adds a role."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from . import workflow as wf
from .role_lens import SESSION_ROLE_KEY, role_functions
from .roles import device_roles
from .models import Device, DeviceMembership

PW = "test-pass-123"


def user(name, *roles):
    u = User.objects.create_user(name, email=f"{name}@example.org", password=PW)
    for r in roles:
        u.groups.add(Group.objects.get_or_create(name=r)[0])
    return u


class ActingAsTests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(name="Device A", code="DA")
        self.both = user("both")  # Engineer and QA on Device A
        DeviceMembership.objects.create(device=self.device, user=self.both,
                                        roles=f"{wf.ENGINEER}, {wf.QA}")
        self.eng = user("eng")  # Engineer only
        DeviceMembership.objects.create(device=self.device, user=self.eng, roles=wf.ENGINEER)

    def choose(self, role):
        return self.client.post(reverse("qms:set_role"), {"role": role,
                                                          "next": reverse("qms:dashboard")})

    def test_all_roles_by_default(self):
        self.client.force_login(self.both)
        resp = self.client.get(reverse("qms:dashboard"))
        self.assertIsNone(resp.context["active_role"])
        self.assertEqual(resp.context["role_options"], [wf.ENGINEER, wf.QA])
        self.assertNotContains(resp, "Acting as</h2>")

    def test_choosing_a_role_limits_the_functions_shown(self):
        self.client.force_login(self.both)
        self.choose(wf.ENGINEER)
        resp = self.client.get(reverse("qms:dashboard"))
        self.assertEqual(resp.context["active_role"], wf.ENGINEER)
        self.assertContains(resp, "Acting as Engineer")
        self.assertNotContains(resp, "Approve document versions")

        self.choose(wf.QA)
        resp = self.client.get(reverse("qms:dashboard"))
        self.assertContains(resp, "Approve document versions")

    def test_choice_limits_permissions_on_the_device(self):
        self.client.force_login(self.both)
        self.choose(wf.ENGINEER)
        resp = self.client.get(reverse("qms:dashboard"))
        self.assertEqual(resp.wsgi_request.user.active_role, wf.ENGINEER)
        self.assertEqual(device_roles(resp.wsgi_request.user, self.device), {wf.ENGINEER})

    def test_cannot_choose_a_role_not_held(self):
        self.client.force_login(self.eng)
        self.choose(wf.QA)
        self.assertNotIn(SESSION_ROLE_KEY, self.client.session)
        resp = self.client.get(reverse("qms:dashboard"))
        self.assertIsNone(resp.context["active_role"])

    def test_a_held_role_no_longer_held_is_dropped(self):
        self.client.force_login(self.eng)
        session = self.client.session
        session[SESSION_ROLE_KEY] = wf.QA  # forged or stale: the person does not hold QA
        session.save()
        resp = self.client.get(reverse("qms:dashboard"))
        self.assertNotIn(SESSION_ROLE_KEY, self.client.session)
        self.assertEqual(device_roles(resp.wsgi_request.user, self.device), {wf.ENGINEER})

    def test_switcher_only_shown_to_people_with_several_roles(self):
        self.client.force_login(self.eng)
        self.assertNotContains(self.client.get(reverse("qms:dashboard")), 'aria-label="Acting as"')
        self.client.force_login(self.both)
        self.assertContains(self.client.get(reverse("qms:dashboard")), 'aria-label="Acting as"')

    def test_return_address_must_be_on_this_site(self):
        self.client.force_login(self.both)
        resp = self.client.post(reverse("qms:set_role"), {"role": wf.QA,
                                                          "next": "https://evil.example/"})
        self.assertRedirects(resp, reverse("qms:dashboard"), fetch_redirect_response=False)

    def test_functions_follow_the_workflow(self):
        engineer = dict(role_functions(wf.ENGINEER))
        self.assertIn("Quality records", engineer)
        self.assertNotIn("Documents, hazards and technical files", engineer)
        self.assertNotIn("Team and access", engineer)
        qa = dict(role_functions(wf.QA))
        self.assertIn("Documents, hazards and technical files", qa)
        self.assertIn("Team and access", qa)
