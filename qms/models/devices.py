"""Medical devices managed by the QMS, and generated technical file packages."""
import os

from django.conf import settings
from django.db import models

from .core import AuditedModel, ImmutableError

CLASSIFICATIONS = [("I", "Class I"), ("IIa", "Class IIa"), ("IIb", "Class IIb"),
                   ("III", "Class III"), ("tbd", "Not yet determined")]
SAFETY_CLASSES = [("A", "Class A"), ("B", "Class B"), ("C", "Class C")]
REG_STATUSES = [("development", "In development"),
                ("clinical_investigation", "Clinical investigation / research use"),
                ("on_market", "On the market"), ("withdrawn", "Withdrawn")]

# Sections of the technical file a controlled document can belong to
# (EU MDR Annex II and III; the UK framework follows the same structure).
TECH_FILE_SECTIONS = [
    ("", "Not part of the technical file"),
    ("description", "1. Device description and specification"),
    ("labelling", "2. Information supplied by the manufacturer (labels, IFU)"),
    ("design", "3. Design and manufacturing information"),
    ("gspr", "4. General safety and performance requirements"),
    ("risk", "5. Benefit-risk analysis and risk management"),
    ("verification", "6. Product verification and validation"),
    ("clinical", "6. Clinical evaluation and usability"),
    ("pms", "7. Post-market surveillance"),
    ("declaration", "8. Declaration of conformity"),
]


class Device(AuditedModel):
    AUDITED = ["name", "code", "description", "intended_purpose", "intended_users",
               "patient_population", "contraindications", "classification",
               "classification_rule", "software_safety_class", "basic_udi_di", "manufacturer",
               "uk_responsible_person", "approved_body", "regulatory_status", "markets",
               "standards_applied", "current_version", "software_items", "owner_id", "active"]

    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=12, unique=True,
                            help_text="Short code shown in lists and emails, e.g. HRT1.")
    description = models.TextField("Description and principle of operation", blank=True)
    intended_purpose = models.TextField(blank=True)
    intended_users = models.TextField(blank=True)
    patient_population = models.TextField("Intended patient population", blank=True)
    contraindications = models.TextField("Contraindications and limitations", blank=True)
    classification = models.CharField(max_length=5, choices=CLASSIFICATIONS, default="tbd")
    classification_rule = models.TextField(
        "Classification rationale", blank=True,
        help_text="Rule applied and why, e.g. MDR Annex VIII Rule 11.")
    software_safety_class = models.CharField("IEC 62304 software safety class", max_length=1,
                                             choices=SAFETY_CLASSES, blank=True)
    basic_udi_di = models.CharField("Basic UDI-DI", max_length=60, blank=True)
    manufacturer = models.TextField("Legal manufacturer (name and address)", blank=True)
    uk_responsible_person = models.TextField("UK Responsible Person / authorised rep.",
                                             blank=True)
    approved_body = models.CharField("Approved / notified body", max_length=200, blank=True)
    regulatory_status = models.CharField(max_length=30, choices=REG_STATUSES,
                                         default="development")
    markets = models.CharField(max_length=200, blank=True, help_text="e.g. UK (UKCA), EU (CE)")
    standards_applied = models.TextField(
        blank=True, help_text="Harmonised / recognised standards applied, one per line.")
    current_version = models.CharField("Current software version", max_length=50, blank=True)
    software_items = models.TextField(
        "Software items", blank=True,
        help_text="The device's main software items (IEC 62304 architecture), one per line.")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="owned_devices")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def audit_ref(self):
        return self.code

    def software_item_list(self) -> list:
        """The device's software items, in the order entered, without blanks or duplicates."""
        items = []
        for line in (self.software_items or "").splitlines():
            line = line.strip()
            if line and line.lower() not in {i.lower() for i in items}:
                items.append(line)
        return items

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)


class DeviceMembership(AuditedModel):
    """A person on a device's team, with their roles on that device. People can be on any
    number of teams, with different roles on each."""
    AUDITED = ["device_id", "user_id", "active", "roles", "note"]

    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name="device_memberships")
    active = models.BooleanField(default=True)
    roles = models.CharField(
        max_length=200, blank=True,
        help_text="Roles on this device, separated by commas: Engineer, QA, Clinical Safety "
                  "Officer, Device admin.")
    note = models.CharField(max_length=200, blank=True,
                            help_text="Responsibility on this device, e.g. 'Lead developer'.")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("device", "user")]
        ordering = ["device__name", "user__username"]

    def __str__(self):
        return f"{self.user.get_username()} @ {self.device.code}"

    def role_list(self) -> list:
        """Roles on this device, in the standard order."""
        from .. import workflow as wf
        held = {r.strip() for r in (self.roles or "").split(",") if r.strip()}
        return [r for r in wf.ROLES if r in held]

    def clean(self):
        """Admin edits the roles as text: refuse names that aren't roles."""
        from django.core.exceptions import ValidationError
        from .. import workflow as wf
        unknown = {r.strip() for r in (self.roles or "").split(",") if r.strip()} - set(wf.ROLES)
        if unknown:
            raise ValidationError({"roles": f"Unknown role(s): {', '.join(sorted(unknown))}. "
                                            f"Use: {', '.join(wf.ROLES)}."})

    def set_roles(self, roles) -> None:
        from .. import workflow as wf
        unknown = set(roles) - set(wf.ROLES)
        if unknown:
            raise ValueError(f"Unknown role(s): {', '.join(sorted(unknown))}")
        self.roles = ", ".join(r for r in wf.ROLES if r in set(roles))


def techfile_path(instance, filename):
    return f"technical_files/{instance.device.code}/{os.path.basename(filename)}"


class TechnicalFileBuild(AuditedModel):
    """A generated technical file package: frozen once generated, signed when approved."""
    STATUSES = [("generated", "Generated"), ("approved", "Approved"),
                ("superseded", "Superseded")]
    AUDITED = ["device_id", "label", "status", "sha256", "error_count", "warning_count"]

    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="technical_files")
    label = models.CharField(max_length=60, help_text="e.g. TF-HRT1-003")
    software_version = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default="generated",
                              editable=False)
    package = models.FileField(upload_to=techfile_path)
    sha256 = models.CharField(max_length=64, editable=False)
    size = models.PositiveBigIntegerField(default=0, editable=False)
    error_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    checks = models.JSONField(default=list, blank=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                     on_delete=models.PROTECT, related_name="+")
    generated_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-generated_at"]
        unique_together = [("device", "label")]

    def __str__(self):
        return self.label

    @property
    def audit_ref(self):
        return self.label

    def check_editable(self, old, via_workflow):
        if old is None:
            return
        if not via_workflow:
            raise ImmutableError("Technical file packages cannot be changed after generation.")
        if old.package.name != self.package.name or old.sha256 != self.sha256:
            raise ImmutableError("A generated package's contents are frozen.")

    def verify(self) -> bool:
        from .core import sha256_of
        with self.package.open("rb") as f:
            return sha256_of(f) == self.sha256
