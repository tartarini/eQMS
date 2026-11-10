"""Tests for multi-device support and technical file generation."""
import hashlib
import io
import json
import shutil
import tempfile
import zipfile

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from . import services, techfile
from . import workflow as wf
from .models import (AuditEvent, Device, DeviceMembership, Document, Hazard, ImmutableError, PMSSchedule, Record,
                     RiskControl, Signature, SoupItem, TechnicalFileBuild)
from .services import TransitionError

PW = "test-pass-123"
MEDIA = tempfile.mkdtemp(prefix="qms-test-devices-")


def make_user(username, role):
    u = User.objects.create_user(username, email=f"{username}@example.org", password=PW)
    u.groups.add(Group.objects.get_or_create(name=role)[0])
    return u


def join(device, *users):
    for u in users:
        DeviceMembership.objects.get_or_create(device=device, user=u)


def complete_device(code="SKN", name="SkinCheck"):
    d = Device(name=name, code=code, description="Photo capture and classification model",
               intended_purpose="Support referral decisions", intended_users="GPs",
               patient_population="Adults with a skin lesion", eu_classification="IIa",
               uk_classification="IIa",
               software_items="Mobile app\nClassification model",
               classification_rule="Rule 11", software_safety_class="B",
               basic_udi_di="5060000000000ABC", manufacturer="Example Ltd",
               operator_roles="manufacturer",
               standards_applied="IEC 62304\nISO 14971", current_version="2.3.1",
               markets="UK")
    d.save()
    return d


@override_settings(MEDIA_ROOT=MEDIA)
class Base(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.eng = make_user("eng", wf.ENGINEER)
        self.qa = make_user("qa", wf.QA)
        self.qa2 = make_user("qa2", wf.QA)
        self.dev = complete_device()
        join(self.dev, self.eng, self.qa, self.qa2)

    def effective_doc(self, title, section, device="default"):
        doc = Document.objects.create(title=title, doc_type="RPT", tech_file_section=section,
                                      device=self.dev if device == "default" else device)
        v = services.create_version(doc, self.eng, version="1.0", change_summary="x",
                                    file=SimpleUploadedFile(f"{title}.pdf", b"%PDF " + title.encode()))
        services.submit_version(v, self.eng)
        services.approve_version(v, self.qa, PW)
        services.make_effective(v, self.qa)
        return v

    def accepted_hazard(self, device=None):
        h = Hazard(device=device or self.dev, title="False negative", hazard="Missed decline",
                   harm="Delayed diagnosis", severity_initial=2, probability_initial=2,
                   severity_residual=2, probability_residual=1)
        h.save()
        services.accept_hazard(h, self.qa, PW)
        return h

    def make_complete(self):
        for code, _ in techfile.EXPECTED_SECTIONS + [("declaration", "")]:
            self.effective_doc(f"Doc {code}", code)
        self.accepted_hazard()
        soup = SoupItem.objects.create(name="numpy", version="2.1", purpose="arrays",
                                       last_anomaly_review=__import__("datetime").date.today())
        soup.devices.add(self.dev)


class DeviceScopingTests(Base):
    def test_pms_setup_per_device_and_activities_carry_device(self):
        other = complete_device("RSPT", "RespiTrack")
        join(other, self.eng, self.qa, self.qa2)
        self.assertEqual(len(services.setup_device_pms(self.dev)), 9)
        self.assertEqual(services.setup_device_pms(self.dev), [])  # idempotent
        services.setup_device_pms(other)
        created = services.generate_pms_activities(horizon_days=400)
        self.assertTrue(created)
        self.assertEqual({r.device for r in created}, {self.dev, other})
        self.assertEqual(PMSSchedule.objects.filter(device=self.dev).count(), 9)

    def test_switcher_filters_lists(self):
        other = complete_device("RSPT", "RespiTrack")
        join(other, self.eng, self.qa, self.qa2)
        Record.objects.create(device=self.dev, record_type=wf.PROBLEM_REPORT, title="A-problem")
        Record.objects.create(device=other, record_type=wf.PROBLEM_REPORT, title="B-problem")
        self.client.login(username="eng", password=PW)
        resp = self.client.get(reverse("qms:record_list"))
        self.assertContains(resp, "A-problem")
        self.assertContains(resp, "B-problem")
        self.client.post(reverse("qms:set_device"), {"device": other.pk, "next": "/records/"})
        resp = self.client.get(reverse("qms:record_list"))
        self.assertNotContains(resp, "A-problem")
        self.assertContains(resp, "B-problem")
        self.assertContains(self.client.get(reverse("qms:dashboard")), "RespiTrack")
        self.client.post(reverse("qms:set_device"), {"device": ""})
        self.assertContains(self.client.get(reverse("qms:record_list")), "A-problem")

    def test_switcher_rejects_external_redirect(self):
        self.client.login(username="eng", password=PW)
        resp = self.client.post(reverse("qms:set_device"),
                                {"device": self.dev.pk, "next": "https://evil.example/"})
        self.assertEqual(resp["Location"], reverse("qms:dashboard"))

    def test_only_qa_creates_devices_and_pms_is_scheduled(self):
        self.client.login(username="eng", password=PW)
        self.client.post(reverse("qms:device_create"), {"name": "X", "code": "x",
                                                       "classification": "tbd",
                                                       "regulatory_status": "development"})
        self.assertFalse(Device.objects.filter(code="X").exists())
        self.client.login(username="qa", password=PW)
        resp = self.client.post(reverse("qms:device_create"), {
            "name": "New device", "code": "nd", "classification": "tbd",
            "regulatory_status": "development", "active": "on"})
        self.assertRedirects(resp, reverse("qms:device_detail", args=["ND"]))
        self.assertEqual(PMSSchedule.objects.filter(device__code="ND").count(), 9)

    def test_device_changes_and_soup_links_are_audited(self):
        self.dev.current_version = "2.4.0"
        self.dev.save()
        ev = AuditEvent.objects.filter(object_ref="SKN", action="update").last()
        self.assertEqual(ev.changes["current_version"], ["2.3.1", "2.4.0"])
        s = SoupItem.objects.create(name="torch", version="2", purpose="x")
        s.devices.add(self.dev)
        self.assertEqual(AuditEvent.for_object(s).last().changes["devices"], {"added": ["SKN"]})

    def test_records_must_have_a_device(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Record.objects.create(record_type=wf.PROBLEM_REPORT, title="orphan")


class CompletenessTests(Base):
    def levels(self, device):
        checks = techfile.completeness_checks(device)
        return ([c["message"] for c in checks if c["level"] == "error"],
                [c["message"] for c in checks if c["level"] == "warning"])

    def test_each_framework_offers_its_own_classes(self):
        from .forms import DeviceForm
        fields = DeviceForm().fields

        def offered(name):
            return [c for c, _ in fields[name].choices]
        self.assertEqual(offered("eu_classification"),
                         ["", "I", "Is", "Im", "Ir", "IIa", "IIb", "III", "tbd"])
        self.assertEqual(offered("uk_classification"), ["", "I", "IIa", "IIb", "III", "tbd"])
        self.assertEqual(offered("us_classification"), ["", "I", "II", "III", "tbd"])
        self.dev.eu_classification, self.dev.uk_classification = "Im", "IIa"
        self.dev.us_classification = "II"
        self.dev.save()
        self.assertEqual(self.dev.classifications(),
                         [("EU MDR", "Class Im (measuring function)"),
                          ("UK MDR 2002", "Class IIa"), ("FDA", "Class II")])
        self.assertEqual(self.dev.classification_summary(), "EU MDR Class Im (measuring "
                         "function) · UK MDR 2002 Class IIa · FDA Class II")
        errors, _ = self.levels(self.dev)
        self.assertFalse(any("classification" in e.lower() for e in errors), errors)

    def test_a_market_with_its_class_not_determined_blocks_approval(self):
        self.dev.us_classification = "tbd"
        self.dev.save()
        errors, _ = self.levels(self.dev)
        self.assertIn("FDA classification has not been determined.", errors)
        self.dev.eu_classification = self.dev.uk_classification = ""
        self.dev.us_classification = ""
        self.dev.save()
        errors, _ = self.levels(self.dev)
        self.assertTrue(any("not set for any market" in e for e in errors))
        self.assertEqual(self.dev.classification_summary(), "Not classified")

    def test_technical_file_lists_the_class_for_each_market(self):
        from django.utils import timezone
        self.dev.us_classification = "II"
        self.dev.save()
        meta = {"label": "SKN-TF-1", "generated_at": timezone.now(), "generated_by": "qa"}
        outline = techfile.build_outline(self.dev, techfile.gather(self.dev), [], meta)
        rows = dict(next(b[1] for b in outline if b[0] == "kv" and
                         any(k == "Device name" for k, _ in b[1])))
        self.assertEqual(rows["Classification (EU MDR)"], "Class IIa")
        self.assertEqual(rows["Classification (UK MDR 2002)"], "Class IIa")
        self.assertEqual(rows["Classification (FDA)"], "Class II")

    def test_empty_device_has_errors(self):
        bare = Device(name="Bare", code="BARE")
        bare.save()
        join(bare, self.eng, self.qa, self.qa2)
        errors, warnings = self.levels(bare)
        joined = " ".join(errors)
        for text in ["Intended purpose", "classification", "software safety class",
                     "no hazards"]:
            self.assertIn(text, joined)
        self.assertTrue(any("Instructions for use" in w for w in warnings))

    def test_complete_device_has_no_gaps(self):
        self.make_complete()
        errors, warnings = self.levels(self.dev)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_on_market_requires_declaration_and_unaccepted_unacceptable_risk_is_error(self):
        self.dev.regulatory_status = "on_market"
        self.dev.save()
        Hazard(device=self.dev, title="Bad", hazard="h", harm="h", severity_initial=5,
               probability_initial=4).save()
        errors, _ = self.levels(self.dev)
        self.assertTrue(any("Declaration of Conformity" in e for e in errors))
        self.assertTrue(any("currently unacceptable" in e for e in errors))

    def test_qms_wide_documents_count_for_every_device(self):
        other = complete_device("RSPT", "RespiTrack")
        join(other, self.eng, self.qa, self.qa2)
        self.effective_doc("Shared PMS SOP", "pms", device=None)
        data = techfile.gather(other)
        self.assertEqual([v.document.title for v in data["sections"]["pms"]], ["Shared PMS SOP"])

    def test_other_devices_data_is_excluded(self):
        other = complete_device("RSPT", "RespiTrack")
        join(other, self.eng, self.qa, self.qa2)
        self.accepted_hazard(device=other)
        Record.objects.create(device=other, record_type=wf.PROBLEM_REPORT, title="Other bug")
        data = techfile.gather(self.dev)
        self.assertEqual(data["hazards"], [])
        self.assertEqual(data["open_anomalies"], [])


class TechnicalFileBuildTests(Base):
    def test_package_contents_manifest_and_formats(self):
        self.make_complete()
        Record.objects.create(device=self.dev, record_type=wf.PROBLEM_REPORT,
                              title="Known anomaly", severity="minor")
        build = techfile.generate_technical_file(self.dev, self.eng)
        self.assertEqual(build.label, "TF-SKN-001")
        self.assertEqual((build.error_count, build.warning_count), (0, 0))
        self.assertTrue(build.verify())

        z = zipfile.ZipFile(build.package.path)
        names = set(z.namelist())
        for expected in ["00_technical_file.html", "00_technical_file.docx", "manifest.json",
                         "registers/risk_register.csv", "registers/soup_list.csv",
                         "registers/audit_trail.csv", "registers/quality_records.csv"]:
            self.assertIn(f"TF-SKN-001/{expected}", names)
        self.assertTrue(any(n.startswith("TF-SKN-001/documents/declaration/") for n in names))

        manifest = json.loads(z.read("TF-SKN-001/manifest.json"))
        for f in manifest["files"]:
            content = z.read(f"TF-SKN-001/{f['path']}")
            self.assertEqual(hashlib.sha256(content).hexdigest(), f["sha256"], f["path"])

        html = z.read("TF-SKN-001/00_technical_file.html").decode()
        for heading in ["1. Device description", "3. Design and manufacturing",
                        "5. Benefit-risk analysis", "7. Post-market surveillance",
                        "Known residual anomalies", "Known anomaly", "Annex A"]:
            self.assertIn(heading, html)
        from docx import Document as Docx
        docx = Docx(io.BytesIO(z.read("TF-SKN-001/00_technical_file.docx")))
        self.assertIn("Technical Documentation", docx.paragraphs[0].text)

        second = techfile.generate_technical_file(self.dev, self.eng)
        self.assertEqual(second.label, "TF-SKN-002")

    def test_builds_are_frozen(self):
        build = techfile.generate_technical_file(self.dev, self.eng)
        build.label = "changed"
        with self.assertRaises(ImmutableError):
            build.save()
        with self.assertRaises(ImmutableError):
            build.delete()

    def test_approval_rules(self):
        bare = Device(name="Bare", code="BARE")
        bare.save()
        join(bare, self.eng, self.qa, self.qa2)
        bad = techfile.generate_technical_file(bare, self.eng)
        with self.assertRaisesMessage(TransitionError, "completeness error"):
            techfile.approve_technical_file(bad, self.qa, PW)

        self.make_complete()
        Record.objects.create(device=self.dev, record_type=wf.INCIDENT, title="Open incident")
        build = techfile.generate_technical_file(self.dev, self.qa)
        self.assertEqual(build.error_count, 0)
        self.assertGreater(build.warning_count, 0)
        with self.assertRaisesMessage(TransitionError, "independent"):
            techfile.approve_technical_file(build, self.qa, PW, "ok")
        with self.assertRaisesMessage(TransitionError, "warning"):
            techfile.approve_technical_file(build, self.qa2, PW, "")
        with self.assertRaisesMessage(TransitionError, "Requires role"):
            techfile.approve_technical_file(build, self.eng, PW, "ok")
        techfile.approve_technical_file(build, self.qa2, PW, "Open incident is under follow-up")
        build.refresh_from_db()
        self.assertEqual(build.status, "approved")
        self.assertTrue(Signature.objects.filter(object_ref=build.label,
                                                 meaning="Technical file approval").exists())

        newer = techfile.generate_technical_file(self.dev, self.qa)
        techfile.approve_technical_file(newer, self.qa2, PW, "Still under follow-up")
        build.refresh_from_db()
        self.assertEqual(build.status, "superseded")

    def test_download_detects_tampering(self):
        build = techfile.generate_technical_file(self.dev, self.eng)
        self.client.login(username="eng", password=PW)
        resp = self.client.get(reverse("qms:techfile_download", args=[build.pk]))
        self.assertEqual(resp.status_code, 200)
        b"".join(resp.streaming_content)
        with open(build.package.path, "ab") as fh:
            fh.write(b"tampered")
        resp = self.client.get(reverse("qms:techfile_download", args=[build.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_pages(self):
        self.make_complete()
        self.client.login(username="qa", password=PW)
        for url in [reverse("qms:device_list"), reverse("qms:device_detail", args=["SKN"]),
                    reverse("qms:device_create"), reverse("qms:device_edit", args=["SKN"])]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        preview = self.client.get(reverse("qms:techfile_preview", args=["SKN"]))
        self.assertContains(preview, "Preview only")
        self.assertContains(preview, "SkinCheck")
        resp = self.client.post(reverse("qms:techfile_generate", args=["SKN"]))
        self.assertRedirects(resp, reverse("qms:device_detail", args=["SKN"]))
        self.assertEqual(TechnicalFileBuild.objects.count(), 1)


class SoftwareItemTests(Base):
    """Software items are defined per device; records, hazards and SOUP use their device's list."""

    def form(self, data, record_type=wf.PROBLEM_REPORT, user=None):
        from .forms import record_form_class
        base = {"device": self.dev.pk, "title": "Crash on upload", "description": "",
                "owner": "", "source": "internal_test", "severity": "minor"}
        return record_form_class(record_type)({**base, **data}, user=user or self.eng)

    def test_list_ignores_blanks_and_duplicates(self):
        d = Device(name="X", code="X1", software_items=" App \n\nModel\napp\n")
        self.assertEqual(d.software_item_list(), ["App", "Model"])

    def test_record_must_use_its_devices_items_and_spelling_is_normalised(self):
        f = self.form({"software_item": "Spell checker"})
        self.assertFalse(f.is_valid())
        self.assertIn("Mobile app, Classification model", f.errors["software_item"][0])
        f = self.form({"software_item": "classification MODEL"})
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.cleaned_data["software_item"], "Classification model")

    def test_device_without_a_list_accepts_any_item(self):
        other = Device.objects.create(name="Other", code="OTH")
        join(other, self.eng)
        f = self.form({"device": other.pk, "software_item": "Anything"})
        self.assertTrue(f.is_valid(), f.errors)

    def test_suggestions_come_only_from_the_users_devices(self):
        hidden = Device.objects.create(name="Hidden", code="HID", software_items="Secret module")
        html = str(self.form({})["software_item"])
        self.assertIn('<option value="Classification model">SKN</option>', html)
        self.assertIn('list="id_software_item_options"', html)
        self.assertNotIn("Secret module", html)
        self.assertTrue(hidden.pk)

    def test_hazard_and_soup_forms_check_items(self):
        from .forms import HazardForm, SoupItemForm
        f = HazardForm({"device": self.dev.pk, "title": "T", "hazard": "H", "harm": "X",
                        "software_item": "Nope", "severity_initial": 2,
                        "probability_initial": 2}, user=self.eng)
        self.assertIn("software_item", f.errors)
        f = SoupItemForm({"name": "Lib", "version": "1", "devices": [self.dev.pk],
                          "software_item": "mobile app", "purpose": "UI", "active": True},
                         user=self.eng)
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.cleaned_data["software_item"], "Mobile app")

    def test_device_page_lists_items(self):
        self.client.login(username="eng", password=PW)
        resp = self.client.get(reverse("qms:device_detail", args=[self.dev.code]))
        self.assertContains(resp, "Mobile app, Classification model")


class SoftwareItemMigrationTests(TransactionTestCase):
    """0003 turns the old fixed codes into their labels and fills each device's list."""

    def test_codes_become_labels_and_device_lists_are_filled(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        executor.migrate([("qms", "0002_devicemembership")])
        apps = executor.loader.project_state([("qms", "0002_devicemembership")]).apps
        OldDevice = apps.get_model("qms", "Device")
        dev = OldDevice.objects.create(name="Legacy", code="LEG")
        empty = OldDevice.objects.create(name="Unused", code="UNU")
        apps.get_model("qms", "Record").objects.create(
            device=dev, record_type="problem_report", ref="PR-9001", title="t",
            software_item="asr")
        apps.get_model("qms", "Hazard").objects.create(
            device=dev, ref="HAZ-901", title="t", software_item="web_app",
            severity_initial=2, probability_initial=2)
        soup = apps.get_model("qms", "SoupItem").objects.create(name="Lib", version="1",
                                                                software_item="scoring_model")
        soup.devices.add(dev)

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes("qms"))
        self.assertEqual(Record.objects.get(ref="PR-9001").software_item, "ASR")
        self.assertEqual(Hazard.objects.get(ref="HAZ-901").software_item, "Web app")
        dev = Device.objects.get(code="LEG")
        self.assertEqual(dev.software_item_list(), ["ASR", "Scoring model", "Web app"])
        self.assertEqual(Device.objects.get(code="UNU").software_items, "")
        self.assertTrue(empty.pk)


class DeviceChoiceTests(TestCase):
    """After sign-in people see their devices and roles, and open one device's QMS."""

    def setUp(self):
        from .test_roles import member, person
        for r in wf.ROLES + (wf.ALL_DEVICES,):
            Group.objects.get_or_create(name=r)
        self.skin = Device.objects.create(name="SkinCheck", code="SKN")
        self.respi = Device.objects.create(name="RespiTrack", code="RSP")
        self.other = Device.objects.create(name="Elsewhere", code="ELS")
        self.user = person("dana")
        member(self.skin, self.user, wf.QA, wf.DEVICE_ADMIN)
        member(self.respi, self.user, wf.ENGINEER)
        member(self.other, person("someone"), wf.QA)

    def test_sign_in_lands_on_the_list_of_your_devices_and_roles(self):
        resp = self.client.post(reverse("login"), {"username": "dana", "password": PW},
                                follow=True)
        self.assertEqual(resp.redirect_chain[-1][0], reverse("qms:device_list"))
        rows = {r["device"].code: r for r in resp.context["rows"]}
        self.assertEqual(set(rows), {"SKN", "RSP"})  # not a device whose team they're not on
        self.assertEqual(rows["SKN"]["roles"], [(wf.QA, False), (wf.DEVICE_ADMIN, False)])
        self.assertEqual(rows["RSP"]["roles"], [(wf.ENGINEER, False)])
        self.assertContains(resp, "Open SkinCheck")
        self.assertContains(resp, "Open RespiTrack")
        self.assertNotContains(resp, "Elsewhere")

    def test_a_link_followed_before_signing_in_still_wins(self):
        resp = self.client.post(reverse("login") + "?next=/records/",
                                {"username": "dana", "password": PW, "next": "/records/"})
        self.assertEqual(resp["Location"], "/records/")

    def test_opening_a_device_loads_its_qms_and_devices_switches_to_another(self):
        self.client.login(username="dana", password=PW)
        Record.objects.create(device=self.skin, record_type=wf.PROBLEM_REPORT, title="Skin bug")
        Record.objects.create(device=self.respi, record_type=wf.PROBLEM_REPORT, title="Respi bug")
        resp = self.client.post(reverse("qms:set_device"),
                                {"device": self.skin.pk, "next": reverse("qms:dashboard")},
                                follow=True)
        self.assertEqual(resp.redirect_chain[-1][0], reverse("qms:dashboard"))
        self.assertContains(resp, "Now working in the SkinCheck QMS")
        records = self.client.get(reverse("qms:record_list"))
        self.assertContains(records, "Skin bug")
        self.assertNotContains(records, "Respi bug")
        listing = self.client.get(reverse("qms:device_list"))
        self.assertTrue(next(r for r in listing.context["rows"]
                             if r["device"] == self.skin)["current"])
        self.client.post(reverse("qms:set_device"), {"device": self.respi.pk})
        records = self.client.get(reverse("qms:record_list"))
        self.assertContains(records, "Respi bug")
        self.assertNotContains(records, "Skin bug")

    def test_cannot_open_a_device_whose_team_you_are_not_on(self):
        self.client.login(username="dana", password=PW)
        self.client.post(reverse("qms:set_device"), {"device": self.other.pk})
        self.assertIsNone(self.client.session.get("qms_device_id"))

    def test_device_admin_alone_sees_the_role_but_no_open_button(self):
        from .test_roles import member, person
        admin = person("admin_only")
        member(self.skin, admin, wf.DEVICE_ADMIN)
        self.client.login(username="admin_only", password=PW)
        resp = self.client.get(reverse("qms:device_list"))
        row = resp.context["rows"][0]
        self.assertEqual(row["roles"], [(wf.DEVICE_ADMIN, False)])
        self.assertFalse(row["can_open"])
        self.assertNotContains(resp, "Open SkinCheck")

    def test_organisation_wide_roles_are_marked(self):
        from .test_roles import person
        head = person("head", wf.QA, wf.ALL_DEVICES)
        self.client.login(username=head.username, password=PW)
        rows = self.client.get(reverse("qms:device_list")).context["rows"]
        self.assertEqual({r["device"].code for r in rows}, {"SKN", "RSP", "ELS"})
        self.assertTrue(all(r["roles"] == [(wf.QA, True)] and r["can_open"] for r in rows))
