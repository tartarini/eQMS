"""Example content for two devices, for trying the QMS. Never run in production."""
from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from qms import services
from qms import workflow as wf
from qms.models import (DISTRIBUTOR_ROLE, MANUFACTURER_ROLE, Organisation, join_operator_roles,
                        Device, DeviceMembership, Document, Hazard, Record, RiskControl, SoupItem, Supplier,
                        TrainingAssignment, TrainingRequirement)

PW = "demo-pass-123"


class Command(BaseCommand):
    help = "Load two example devices with documents, hazards, suppliers and records."

    def handle(self, *args, **options):
        if Device.objects.exists() or Document.objects.exists():
            raise CommandError("Demo data needs an empty database.")
        call_command("seed_qms", "--demo", stdout=self.stdout)
        eng, qa = User.objects.get(username="engineer"), User.objects.get(username="qa")
        qa2, _ = User.objects.get_or_create(username="qa2", defaults={
            "first_name": "QA reviewer", "email": "qa2@example.org"})
        qa2.set_password(PW)
        qa2.save()

        Organisation(name="Example manufacturer Ltd", address="1 Example Street\nSheffield",
                     srn="GB-MF-000000000",
                     roles=join_operator_roles([MANUFACTURER_ROLE, DISTRIBUTOR_ROLE])
                     ).save(_actor=qa)
        skn = Device(
            name="SkinCheck", code="SKN", owner=eng, current_version="2.3.1",
            regulatory_status="clinical_investigation", markets="UK (UKCA)",
            description="Smartphone app: a clinician photographs a skin lesion, an image quality "
                        "check rejects unusable photos, and a classification model estimates "
                        "the likelihood that the lesion needs urgent specialist review.",
            intended_purpose="To support primary-care clinicians in deciding whether to refer "
                             "adults with a suspicious skin lesion urgently. Not for diagnosis.",
            intended_users="GPs and primary-care clinicians.",
            patient_population="Adults with a skin lesion their clinician is unsure about.",
            contraindications="Lesions on mucosa, nails or scalp; images of children.",
            classification="IIa",
            classification_rule="MDR Annex VIII Rule 11: software providing information used to "
                                "take decisions with diagnostic purposes.",
            software_safety_class="B", basic_udi_di="", manufacturer="Example manufacturer Ltd",
            operator_roles=MANUFACTURER_ROLE,
            software_items="Mobile app\nImage quality check\nClassification model\n"
                           "Clinician portal\nInfrastructure",
            standards_applied="IEC 62304:2006+A1:2015\nISO 14971:2019\nIEC 62366-1:2015\n"
                              "ISO 13485:2016")
        skn.save(_actor=qa)
        resp = Device(
            name="RespiTrack", code="RSPT", owner=eng, current_version="0.4.0",
            regulatory_status="development", classification="tbd",
            description="Prototype app estimating breathing rate from phone audio.",
            software_items="Mobile app\nSignal processing\nInfrastructure")
        resp.save(_actor=qa)
        for d in (skn, resp):
            services.setup_device_pms(d)
        cso = User.objects.get(username="cso")
        # Roles are per device. engineer: Engineer on SkinCheck, but Engineer, QA and Device
        # admin on RespiTrack. qa2 (QA) and cso (Clinical Safety Officer): SkinCheck only.
        # qa is head of quality with All-device access.
        teams = [(skn, [(eng, [wf.ENGINEER]), (qa, [wf.DEVICE_ADMIN]), (qa2, [wf.QA]),
                        (cso, [wf.CLINICAL_SAFETY])]),
                 (resp, [(eng, [wf.ENGINEER, wf.QA, wf.DEVICE_ADMIN]), (qa, [])])]
        for device, members in teams:
            for u, roles in members:
                m = DeviceMembership(device=device, user=u)
                m.set_roles(roles)
                m.save(_actor=qa)
        qa.groups.add(Group.objects.get(name=wf.ALL_DEVICES))

        def doc(title, doc_type, section, device, author=eng, approver=qa, effective=True,
                train=()):
            d = Document.objects.create(title=title, doc_type=doc_type, tech_file_section=section,
                                        device=device, owner=author)
            for role in train:
                TrainingRequirement.objects.create(document=d, group=Group.objects.get(name=role))
            v = services.create_version(d, author, version="1.0", change_summary="First issue",
                                        file=ContentFile(f"%PDF-1.4 {title}".encode(),
                                                         name=f"{d.number}.pdf"))
            services.submit_version(v, author)
            if effective:
                services.approve_version(v, approver, PW, "Reviewed")
                services.make_effective(v, qa)
            return d, v

        _, sop = doc("Software problem resolution", "SOP", "", None,
                     train=(wf.ENGINEER, wf.QA))
        services.complete_training(TrainingAssignment.objects.get(user=qa, version=sop), qa, PW)
        doc("Instructions for use", "SPEC", "labelling", skn)
        doc("Software development plan and requirements", "PLAN", "design", skn)
        doc("Risk management plan and report", "RPT", "risk", skn)
        doc("Software verification report", "RPT", "verification", skn)
        doc("Clinical evaluation report", "RPT", "clinical", skn)
        doc("Post-market surveillance plan", "PLAN", "pms", skn, author=qa, approver=qa2)
        doc("GSPR checklist", "FORM", "gspr", skn, effective=False)
        doc("RespiTrack software development plan", "PLAN", "design", resp)

        cr = Record(record_type=wf.CHANGE_REQUEST, device=skn, created_by=eng,
                    title="Refer images near the decision threshold for specialist review")
        cr.save()
        h = Hazard(device=skn, title="Missed melanoma",
                   hazard="Classification model returns a false negative",
                   cause="Model under-performs on skin types under-represented in training data",
                   hazardous_situation="GP receives a low-risk result for a melanoma",
                   harm="Delayed diagnosis and treatment", software_item="Classification model",
                   severity_initial=4, probability_initial=3, owner=eng)
        h.save(_actor=eng)
        RiskControl(hazard=h, control_type="protective", implemented_by=cr,
                    description="Results near the decision threshold are reported as "
                                "inconclusive and referred for specialist review",
                    verification_evidence="Verification report VR-07",
                    verified=True).save(_actor=eng)
        h.severity_residual, h.probability_residual = 4, 1
        h.save(_actor=eng)
        services.accept_hazard(h, qa, PW, "Residual risk acceptable")
        Hazard(device=skn, title="Result sent to wrong GP practice", hazard="Misrouted report",
               harm="Privacy breach; delayed care", software_item="Clinician portal",
               severity_initial=3, probability_initial=2).save(_actor=eng)
        Hazard(device=resp, title="Breathing rate over-estimated in noise",
               hazard="Background noise counted as breaths", harm="False reassurance",
               software_item="Signal processing",
               severity_initial=3, probability_initial=4).save(_actor=eng)

        host = Supplier(name="Cloud hosting provider", category="cloud", criticality="high",
                        scope="Hosts the web apps and data (UK region)")
        host.save(_actor=qa)
        services.evaluate_supplier(host, qa, PW, "approved",
                                   "ISO 27001 and Cyber Essentials Plus reviewed; DPA signed")
        torch = SoupItem(name="PyTorch", version="2.5.1", software_item="Classification model",
                         purpose="Model inference", licence="BSD-3", safety_class="B")
        torch.save(_actor=eng)
        torch.devices.add(skn, resp)
        opencv = SoupItem(name="OpenCV", version="4.10.0", software_item="Image quality check",
                          purpose="Blur and exposure checks on photos", licence="Apache-2.0",
                          safety_class="B")
        opencv.save(_actor=eng)
        opencv.devices.add(skn)

        pr = Record(record_type=wf.PROBLEM_REPORT, device=skn, created_by=eng,
                    title="Blurred photos pass the image quality check", source="clinical_site",
                    severity="major", patient_safety_impact="unknown",
                    software_item="Image quality check",
                    software_version="2.3.1")
        pr.save()
        pr.hazards.add(h)
        Record(record_type=wf.PROBLEM_REPORT, device=resp, created_by=eng,
               title="App crashes when microphone permission denied", severity="minor").save()
        services.generate_pms_activities()
        self.stdout.write(self.style.SUCCESS(
            f"Demo data loaded for {skn} and {resp}. Sign in with password {PW} as engineer "
            "(Engineer on SkinCheck; Engineer, QA and Device admin on RespiTrack), qa (head of "
            "quality: QA everywhere, All-device access), qa2 (QA) or cso (Clinical Safety "
            "Officer), both on SkinCheck only."))
