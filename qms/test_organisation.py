"""The organisation profile and its EU MDR economic operator roles, per device (URS-74)."""
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from . import techfile
from . import workflow as wf
from .forms import DeviceForm, OrganisationForm
from .models import (AUTHORISED_REP_ROLE, DISTRIBUTOR_ROLE, IMPORTER_ROLE, MANUFACTURER_ROLE,
                     AuditEvent, Device, Organisation)
from .test_roles import PW, member, person


def device_data(device, **changes):
    data = {"name": device.name, "code": device.code, "regulatory_status": "development",
            "classification": "tbd", "active": "on"}
    data.update(changes)
    return data


class OrganisationProfileTests(TestCase):
    def setUp(self):
        for r in wf.ROLES + (wf.ALL_DEVICES,):
            Group.objects.get_or_create(name=r)
        self.device = Device.objects.create(name="SkinCheck", code="SKN")
        self.head = person("head", wf.QA)                 # QA organisation-wide
        self.device_qa = person("dqa")
        member(self.device, self.head, wf.QA)
        member(self.device, self.device_qa, wf.QA)       # QA on the device only

    def test_organisation_wide_qa_sets_up_the_profile_and_it_is_audited(self):
        self.client.login(username="head", password=PW)
        resp = self.client.post(reverse("qms:organisation_edit"), {
            "name": "Example Health Ltd", "address": "1 Example Street\nSheffield",
            "srn": "GB-MF-000012345", "roles": [MANUFACTURER_ROLE, DISTRIBUTOR_ROLE]})
        self.assertRedirects(resp, reverse("qms:organisation"))
        org = Organisation.current()
        self.assertEqual(org.role_list(), [MANUFACTURER_ROLE, DISTRIBUTOR_ROLE])
        self.assertEqual(org.roles, "manufacturer, distributor")
        event = AuditEvent.objects.get(object_type="Organisation", action="create")
        self.assertEqual(event.actor, self.head)
        page = self.client.get(reverse("qms:organisation"))
        self.assertContains(page, "GB-MF-000012345")
        self.assertContains(page, "Manufacturer")
        self.assertContains(page, "Distributor")

    def test_device_level_qa_cannot_change_the_profile(self):
        self.client.login(username="dqa", password=PW)
        resp = self.client.post(reverse("qms:organisation_edit"),
                                {"name": "Hijack Ltd", "roles": [IMPORTER_ROLE]})
        self.assertRedirects(resp, reverse("qms:organisation"))
        self.assertIsNone(Organisation.current())
        self.assertNotContains(self.client.get(reverse("qms:organisation")),
                               reverse("qms:organisation_edit"))

    def test_a_role_still_set_on_a_device_cannot_be_removed(self):
        Organisation.objects.create(name="Example Health Ltd",
                                    roles="manufacturer, distributor")
        self.device.operator_roles = DISTRIBUTOR_ROLE
        self.device.save()
        form = OrganisationForm({"name": "Example Health Ltd", "roles": [MANUFACTURER_ROLE]},
                                instance=Organisation.current())
        self.assertFalse(form.is_valid())
        self.assertIn("Distributor on SKN", form.errors["roles"][0])


class DeviceOperatorRoleTests(TestCase):
    def setUp(self):
        for r in wf.ROLES + (wf.ALL_DEVICES,):
            Group.objects.get_or_create(name=r)
        self.device = Device.objects.create(name="SkinCheck", code="SKN")
        self.org = Organisation.objects.create(name="Example Health Ltd",
                                               address="1 Example Street\nSheffield",
                                               roles="manufacturer, importer")

    def test_device_offers_only_the_organisations_roles(self):
        form = DeviceForm(instance=self.device)
        self.assertEqual([c for c, _ in form.fields["operator_roles"].choices],
                         [MANUFACTURER_ROLE, IMPORTER_ROLE])
        form = DeviceForm(device_data(self.device, operator_roles=[DISTRIBUTOR_ROLE]),
                          instance=self.device)
        self.assertFalse(form.is_valid())
        self.assertIn("operator_roles", form.errors)

    def test_a_profile_without_roles_offers_all_four(self):
        Organisation.objects.all().update(roles="")
        form = DeviceForm(device_data(self.device, operator_roles=[AUTHORISED_REP_ROLE]),
                          instance=self.device)
        self.assertEqual(len(form.fields["operator_roles"].choices), 4)
        self.assertTrue(form.is_valid(), form.errors)

    def test_manufacturer_role_fills_in_the_manufacturer_from_the_profile(self):
        form = DeviceForm(device_data(self.device, operator_roles=[MANUFACTURER_ROLE]),
                          instance=self.device)
        self.assertTrue(form.is_valid(), form.errors)
        device = form.save()
        self.assertEqual(device.operator_roles, "manufacturer")
        self.assertEqual(device.manufacturer, "Example Health Ltd\n1 Example Street\nSheffield")

    def test_an_entered_manufacturer_is_kept(self):
        form = DeviceForm(device_data(self.device, operator_roles=[IMPORTER_ROLE],
                                      manufacturer="Overseas Devices Inc\nBoston"),
                          instance=self.device)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().manufacturer, "Overseas Devices Inc\nBoston")

    def test_role_shows_on_the_device_page_and_in_the_technical_file(self):
        self.device.operator_roles = IMPORTER_ROLE
        self.device.save()
        eng = person("eng")
        member(self.device, eng, wf.ENGINEER)
        self.client.login(username="eng", password=PW)
        page = self.client.get(reverse("qms:device_detail", args=["SKN"]))
        self.assertContains(page, "Our role")
        self.assertContains(page, "Importer")
        from django.utils import timezone
        meta = {"label": "SKN-TF-1", "generated_at": timezone.now(), "generated_by": "eng"}
        outline = techfile.build_outline(self.device, techfile.gather(self.device), [], meta)
        rows = dict(next(b[1] for b in outline if b[0] == "kv" and
                         any(k == "Device name" for k, _ in b[1])))
        self.assertEqual(rows["Organisation's role for this device"], "Importer")
        self.assertEqual(rows["Organisation"], "Example Health Ltd\n1 Example Street\nSheffield")

    def test_completeness_check_warns_until_the_role_is_set(self):
        def warned():
            return any("economic operator role" in c["message"]
                       for c in techfile.completeness_checks(self.device)
                       if c["level"] == "warning")
        self.assertTrue(warned())
        self.device.operator_roles = MANUFACTURER_ROLE
        self.device.save()
        self.assertFalse(warned())
