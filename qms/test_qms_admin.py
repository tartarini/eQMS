"""The QMS admin group: manages the application overall and is the only one who may appoint or
remove Device admins. Device admins keep managing the other roles on their own teams."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from . import workflow as wf
from .invitations import create_invitation
from .models import AuditEvent, Device, DeviceMembership
from .roles import can_manage_team, is_qms_admin
from .services import TransitionError

PW = "test-pass-123"


def user(name, *roles):
    u = User.objects.create_user(name, email=f"{name}@example.org", password=PW)
    for r in roles:
        u.groups.add(Group.objects.get_or_create(name=r)[0])
    return u


class QmsAdminTests(TestCase):
    def setUp(self):
        self.dev = Device.objects.create(name="Device A", code="DA")
        self.other = Device.objects.create(name="Device B", code="DB")
        self.qms_admin = user("qms_admin", wf.QMS_ADMIN)
        self.dev_admin = user("dev_admin", wf.ENGINEER)
        self.second_admin = user("second_admin", wf.ENGINEER)
        self.engineer = user("engineer", wf.ENGINEER)
        self.newbie = user("newbie")
        DeviceMembership.objects.create(device=self.dev, user=self.dev_admin,
                                        roles=f"{wf.ENGINEER}, {wf.DEVICE_ADMIN}")
        DeviceMembership.objects.create(device=self.dev, user=self.second_admin,
                                        roles=f"{wf.ENGINEER}, {wf.DEVICE_ADMIN}")
        DeviceMembership.objects.create(device=self.dev, user=self.engineer, roles=wf.ENGINEER)
        self.m_second = DeviceMembership.objects.get(device=self.dev, user=self.second_admin)
        self.m_engineer = DeviceMembership.objects.get(device=self.dev, user=self.engineer)

    def login(self, u):
        self.client.force_login(u)

    def test_qms_admin_sees_and_manages_every_device_without_a_membership(self):
        self.assertTrue(is_qms_admin(self.qms_admin))
        self.assertTrue(can_manage_team(self.qms_admin, self.other))
        self.login(self.qms_admin)
        resp = self.client.get(reverse("qms:device_detail", args=[self.other.code]))
        self.assertEqual(resp.status_code, 200)

    def test_ordinary_user_is_not_a_qms_admin(self):
        self.assertFalse(is_qms_admin(self.newbie))
        self.assertFalse(can_manage_team(self.engineer, self.other))

    def test_device_admin_cannot_add_a_device_admin(self):
        self.login(self.dev_admin)
        self.client.post(reverse("qms:team_add", args=[self.dev.code]),
                         {"user": self.newbie.pk, "roles": [wf.DEVICE_ADMIN]})
        self.assertFalse(DeviceMembership.objects.filter(
            device=self.dev, user=self.newbie, active=True).exists())

    def test_device_admin_cannot_remove_device_admin_from_another_admin(self):
        self.login(self.dev_admin)
        self.client.post(reverse("qms:team_roles", args=[self.m_second.pk]),
                         {f"m{self.m_second.pk}-roles": [wf.ENGINEER],
                          f"m{self.m_second.pk}-note": ""})
        self.m_second.refresh_from_db()
        self.assertIn(wf.DEVICE_ADMIN, self.m_second.role_list())

    def test_device_admin_cannot_remove_a_device_admin_from_the_team(self):
        self.login(self.dev_admin)
        self.client.post(reverse("qms:team_remove", args=[self.m_second.pk]))
        self.m_second.refresh_from_db()
        self.assertTrue(self.m_second.active)

    def test_device_admin_can_still_change_ordinary_roles(self):
        self.login(self.dev_admin)
        self.client.post(reverse("qms:team_roles", args=[self.m_engineer.pk]),
                         {f"m{self.m_engineer.pk}-roles": [wf.ENGINEER, wf.QA],
                          f"m{self.m_engineer.pk}-note": ""})
        self.m_engineer.refresh_from_db()
        self.assertIn(wf.QA, self.m_engineer.role_list())

    def test_qms_admin_appoints_a_device_admin_and_it_is_audited(self):
        self.login(self.qms_admin)
        self.client.post(reverse("qms:team_roles", args=[self.m_engineer.pk]),
                         {f"m{self.m_engineer.pk}-roles": [wf.ENGINEER, wf.DEVICE_ADMIN],
                          f"m{self.m_engineer.pk}-note": ""})
        self.m_engineer.refresh_from_db()
        self.assertIn(wf.DEVICE_ADMIN, self.m_engineer.role_list())
        self.assertTrue(AuditEvent.objects.filter(object_type="Device Membership",
                                                  object_ref__endswith="@ DA").exists())

    def test_qms_admin_removes_a_device_admin(self):
        self.login(self.qms_admin)
        self.client.post(reverse("qms:team_roles", args=[self.m_second.pk]),
                         {f"m{self.m_second.pk}-roles": [wf.ENGINEER],
                          f"m{self.m_second.pk}-note": ""})
        self.m_second.refresh_from_db()
        self.assertNotIn(wf.DEVICE_ADMIN, self.m_second.role_list())

    def test_device_admin_cannot_invite_as_device_admin(self):
        with self.assertRaises(TransitionError):
            create_invitation(self.dev_admin, "new@example.org",
                              {self.dev: [wf.DEVICE_ADMIN]})

    def test_device_admin_can_still_invite_an_engineer(self):
        invitation, _ = create_invitation(self.dev_admin, "new@example.org",
                                          {self.dev: [wf.ENGINEER]})
        self.assertEqual(invitation.email, "new@example.org")

    def test_qms_admin_can_invite_as_device_admin(self):
        invitation, _ = create_invitation(self.qms_admin, "new@example.org",
                                          {self.dev: [wf.DEVICE_ADMIN]})
        self.assertEqual(invitation.email, "new@example.org")
