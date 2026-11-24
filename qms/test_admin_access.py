"""Django admin only through the SSH tunnel on production (finding F7)."""
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse, set_script_prefix

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

    @override_settings(QMS_ADMIN_HOSTS=[TUNNEL], ALLOWED_HOSTS=["qms.example.org", "localhost"],
                       FORCE_SCRIPT_NAME="/qms")
    def test_admin_stays_on_the_tunnel_under_a_sub_path(self):
        # The proxy removes /qms before the app sees the request, so the rule must match /admin/
        # here, and the admin link must carry the prefix. The WSGI handler sets the script prefix
        # for each request; the test client does not, so set it as the handler would.
        set_script_prefix("/qms/")
        self.addCleanup(set_script_prefix, "/")
        public = {"HTTP_HOST": "qms.example.org"}
        self.assertEqual(self.client.get("/admin/", **public).status_code, 404)
        self.assertEqual(self.client.get("/admin/auth/user/", **public).status_code, 404)
        tunnel = {"HTTP_HOST": TUNNEL}
        self.assertEqual(self.client.get("/admin/", **tunnel).status_code, 200)
        self.assertContains(self.client.get("/", **tunnel), 'href="/qms/admin/"')
