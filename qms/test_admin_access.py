"""Django admin only through the SSH tunnel on production (finding F7)."""
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from . import workflow as wf
from .models import Device
from .test_roles import member, person

TUNNEL = "localhost:8443"


class AdminAccessTests(TestCase):
    def setUp(self):
        for r in wf.ROLES + (wf.ALL_DEVICES,):
            Group.objects.get_or_create(name=r)
        self.staff = person("staffer")
        self.staff.is_staff = True
        self.staff.is_superuser = True
        self.staff.save()
        member(Device.objects.create(name="Device A", code="DA"), self.staff, wf.QA)
        self.client.force_login(self.staff)

    def test_admin_answers_everywhere_when_no_hosts_are_set(self):
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertContains(self.client.get(reverse("qms:dashboard")), 'href="/admin/"')

    @override_settings(QMS_ADMIN_HOSTS=[TUNNEL], ALLOWED_HOSTS=["qms.example.org", "localhost"])
    def test_admin_only_through_the_tunnel_host(self):
        public = {"HTTP_HOST": "qms.example.org"}
        self.assertEqual(self.client.get("/admin/", **public).status_code, 404)
        self.assertEqual(self.client.get("/admin/login/", **public).status_code, 404)
        self.assertEqual(self.client.get("/admin/auth/user/", **public).status_code, 404)
        self.assertNotContains(self.client.get(reverse("qms:dashboard"), **public),
                               'href="/admin/"')
        tunnel = {"HTTP_HOST": TUNNEL}
        self.assertEqual(self.client.get("/admin/", **tunnel).status_code, 200)
        self.assertContains(self.client.get(reverse("qms:dashboard"), **tunnel),
                            'href="/admin/"')
