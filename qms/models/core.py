import hashlib
import json
import os
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils import timezone

from .. import workflow as wf
from ..current_user import get_current_user

YES_NO_UNKNOWN = [("yes", "Yes"), ("no", "No"), ("unknown", "Unknown")]



class ImmutableError(Exception):
    """Raised when code tries to change or delete an append-only or locked record."""


class QMSJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        try:
            return super().default(o)
        except TypeError:
            return str(o)  # files, model instances, etc.


# ---------------------------------------------------------------------------
# Audit trail: append-only and hash-chained, so any edit to history is detectable.
# ---------------------------------------------------------------------------

class AuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ImmutableError("Audit events cannot be updated.")

    def delete(self):
        raise ImmutableError("Audit events cannot be deleted.")


class AuditEvent(models.Model):
    ACTIONS = [
        ("create", "Created"), ("update", "Updated"), ("transition", "Status change"),
        ("sign", "Signed"), ("link", "Linked"), ("unlink", "Unlinked"),
        ("attach", "File attached"), ("security", "Security"),
    ]
    record = models.ForeignKey("Record", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="audit_events")
    # For anything that isn't a Record (documents, hazards, suppliers…)
    object_type = models.CharField(max_length=50, blank=True, db_index=True)
    object_ref = models.CharField(max_length=60, blank=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.PROTECT)
    actor_name = models.CharField(max_length=150, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, editable=False)
    action = models.CharField(max_length=20, choices=ACTIONS)
    changes = models.JSONField(default=dict, blank=True)
    comment = models.TextField(blank=True)
    prev_hash = models.CharField(max_length=64, editable=False)
    hash = models.CharField(max_length=64, editable=False, unique=True)

    objects = AuditQuerySet.as_manager()

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.actor_name or 'system'} {self.action}"

    @property
    def subject(self):
        if self.record_id:
            return self.record.ref
        return f"{self.object_type} {self.object_ref}".strip()

    @property
    def change_lines(self):
        """(field, readable value) pairs; [old, new] pairs become 'old → new'."""
        def fmt(v):
            return "—" if v in (None, "", []) else str(v)
        lines = []
        for key, value in (self.changes or {}).items():
            if isinstance(value, list) and len(value) == 2:
                text = f"{fmt(value[0])} → {fmt(value[1])}"
            elif isinstance(value, dict):
                text = "; ".join(f"{k}: {fmt(v)}" for k, v in value.items())
            else:
                text = fmt(value)
            lines.append((key.replace("_id", "").replace("_", " "), text))
        return lines

    def payload(self) -> str:
        data = {
            "record": self.record_id,
            "actor": self.actor_id,
            "actor_name": self.actor_name,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "changes": self.changes,
            "comment": self.comment,
            "prev_hash": self.prev_hash,
        }
        if self.object_type or self.object_ref:
            data["object_type"], data["object_ref"] = self.object_type, self.object_ref
        return json.dumps(data, sort_keys=True, default=str)

    def compute_hash(self) -> str:
        return hashlib.sha256(self.payload().encode()).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableError("Audit events cannot be modified.")
        with transaction.atomic():
            last = AuditEvent.objects.select_for_update().order_by("-id").first()
            self.prev_hash = last.hash if last else "0" * 64
            self.hash = self.compute_hash()
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError("Audit events cannot be deleted.")

    @classmethod
    def log(cls, action, record=None, obj=None, actor=None, changes=None, comment=""):
        actor = actor if actor is not None else get_current_user()
        if actor is not None and not getattr(actor, "is_authenticated", False):
            actor = None
        if obj is not None and isinstance(obj, Record):
            record, obj = obj, None
        # Normalise to plain JSON so the hash is identical after a database round-trip.
        changes = json.loads(json.dumps(changes or {}, cls=QMSJSONEncoder))
        return cls.objects.create(
            record=record,
            object_type=(obj.audit_type if obj is not None else ""),
            object_ref=(obj.audit_ref if obj is not None else ""),
            actor=actor, actor_name=(actor.get_username() if actor else "system"),
            action=action, changes=changes, comment=comment,
        )

    @classmethod
    def for_object(cls, obj):
        if isinstance(obj, Record):
            return cls.objects.filter(record=obj)
        return cls.objects.filter(object_type=obj.audit_type, object_ref=obj.audit_ref)


def verify_audit_chain():
    """Return (ok, first_bad_event_id or None)."""
    prev = "0" * 64
    for event in AuditEvent.objects.order_by("id").iterator():
        if event.prev_hash != prev or event.compute_hash() != event.hash:
            return False, event.id
        prev = event.hash
    return True, None


def _readable_snapshot(obj, field_names):
    """Field values for the audit trail; foreign keys are recorded by name, not database id."""
    snap = {}
    for f in field_names:
        if f.endswith("_id"):
            related = getattr(obj, f[:-3])
            key = f[:-3]
            snap[key] = str(related) if related is not None else None
        else:
            snap[f] = getattr(obj, f)
    return snap


class AuditedModel(models.Model):
    """
    Base for QMS objects: logs creation and every change to ``AUDITED`` fields,
    can't be deleted, and can refuse edits via ``check_editable``.
    """
    AUDITED: list = []

    class Meta:
        abstract = True

    @property
    def audit_type(self):
        return self._meta.verbose_name.title()

    @property
    def audit_ref(self):
        return str(self)[:60]

    def _snapshot(self):
        return _readable_snapshot(self, self.AUDITED)

    def state_hash(self) -> str:
        data = {"type": self.audit_type, "ref": self.audit_ref, **self._snapshot()}
        return hashlib.sha256(json.dumps(data, sort_keys=True, cls=QMSJSONEncoder)
                              .encode()).hexdigest()

    def check_editable(self, old, via_workflow):
        """Override to refuse changes; raise ImmutableError."""

    def save(self, *args, _via_workflow=False, _actor=None, _comment="", **kwargs):
        creating = self.pk is None
        old = None if creating else type(self).objects.get(pk=self.pk)
        self.check_editable(old, _via_workflow)
        with transaction.atomic():
            super().save(*args, **kwargs)
            if creating:
                AuditEvent.log("create", obj=self, actor=_actor, comment=_comment, changes={
                    k: [None, v] for k, v in self._snapshot().items() if v not in ("", None)})
            else:
                before, after = old._snapshot(), self._snapshot()
                diff = {k: [before[k], after[k]] for k in before if before[k] != after[k]}
                if diff:
                    action = "transition" if "status" in diff else "update"
                    AuditEvent.log(action, obj=self, actor=_actor, comment=_comment,
                                   changes=diff)

    def delete(self, *args, **kwargs):
        raise ImmutableError(f"{self.audit_type} records are never deleted.")


# ---------------------------------------------------------------------------
# Quality records
# ---------------------------------------------------------------------------

AUDITED_FIELDS = [
    "device_id", "title", "description", "owner_id",
    "source", "severity", "patient_safety_impact", "software_version", "software_item",
    "soup_involved", "risk_file_updated", "date_aware", "reportable",
    "reportability_rationale", "deadline_category", "mhra_reference", "investigation_summary",
    "root_cause", "impact_analysis", "verification_evidence", "effectiveness_due", "fix_version",
    "resolution", "due_date", "period_start", "period_end",
    "audit_scope", "auditee_id", "planned_date", "attendees", "review_inputs", "resource_needs",
    "nc_disposition", "concession_justification", "design_element", "acceptance_criteria",
]


class Record(models.Model):
    SEVERITY = [("critical", "Critical"), ("major", "Major"), ("minor", "Minor"),
                ("cosmetic", "Cosmetic")]
    SOURCE = [("internal_test", "Internal test"), ("clinical_site", "Clinical site"),
              ("gp", "GP"), ("patient_carer", "Patient / carer"), ("literature", "Literature"),
              ("regulator", "Regulator"), ("other", "Other")]
    RISK_FILE = [("yes", "Yes"), ("not_needed", "Not needed"), ("pending", "Pending")]
    REPORTABLE = [("yes", "Yes"), ("no", "No"), ("pending", "Pending")]

    ref = models.CharField(max_length=20, unique=True, editable=False)
    record_type = models.CharField(max_length=30, choices=wf.RECORD_TYPES)
    device = models.ForeignKey("Device", on_delete=models.PROTECT, related_name="records",
                               help_text="The medical device this record is about.")
    status = models.CharField(max_length=30, choices=wf.state_choices(), editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(
        blank=True,
        help_text="No patient or participant data: no names, NHS or hospital numbers, "
                  "identifiable images or recordings. Use anonymised site or study IDs.")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="owned_records")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="created_records",
                                   editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)

    # Classification
    source = models.CharField(max_length=30, choices=SOURCE, blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY, blank=True)
    patient_safety_impact = models.CharField(max_length=10, choices=YES_NO_UNKNOWN, blank=True)
    software_version = models.CharField(max_length=50, blank=True)
    software_item = models.CharField(max_length=100, blank=True)
    soup_involved = models.BooleanField(default=False, verbose_name="SOUP involved")

    # Risk
    hazards = models.ManyToManyField("Hazard", blank=True, related_name="records",
                                     help_text="Hazards in the risk register this record affects.")
    risk_file_updated = models.CharField(max_length=20, choices=RISK_FILE, blank=True)

    # Complaints and vigilance
    date_aware = models.DateField(null=True, blank=True,
                                  help_text="Day the team first became aware. Starts the clock.")
    reportable = models.CharField("Reportable to MHRA", max_length=10, choices=REPORTABLE,
                                  blank=True)
    reportability_rationale = models.TextField(blank=True)
    deadline_category = models.CharField(
        max_length=30, blank=True,
        choices=[(k, v["label"]) for k, v in settings.QMS_VIGILANCE_DEADLINES.items()])
    mhra_reference = models.CharField("MHRA reference", max_length=50, blank=True)

    # Investigation and outcome
    investigation_summary = models.TextField("Investigation summary / findings", blank=True)
    root_cause = models.TextField(blank=True)
    impact_analysis = models.TextField(
        blank=True, help_text="Impact on risk, requirements, tests and regression scope.")
    verification_evidence = models.CharField(max_length=300, blank=True,
                                             help_text="Link to test run, PR or report.")
    effectiveness_due = models.DateField("Effectiveness check due", null=True, blank=True)
    fix_version = models.CharField(max_length=50, blank=True)
    resolution = models.TextField("Resolution / outcome", blank=True)

    # PMS
    due_date = models.DateField(null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    pms_schedule = models.ForeignKey("PMSSchedule", null=True, blank=True,
                                     on_delete=models.PROTECT, related_name="activities")

    # Internal audit (8.2.4)
    audit_scope = models.TextField(
        "Audit scope", blank=True,
        help_text="The clauses, processes, documents or areas being audited.")
    auditee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="audited_records",
        help_text="The person responsible for the area audited. Must not be the lead auditor.")

    # Management review (5.6), design review (7.3.5)
    planned_date = models.DateField(null=True, blank=True)
    attendees = models.TextField(blank=True)
    review_inputs = models.TextField(
        "Review inputs", blank=True,
        help_text="What was reviewed: feedback, complaints, reports to regulators, audits, "
                  "process and product monitoring, CAPA, changes affecting the QMS, "
                  "recommendations, and new regulatory requirements.")
    resource_needs = models.TextField("Resource needs", blank=True)

    # Nonconforming product (8.3)
    nc_disposition = models.CharField(
        "Disposition", max_length=30, blank=True, choices=wf.NC_DISPOSITIONS)
    concession_justification = models.TextField(
        "Concession justification", blank=True,
        help_text="Why the nonconforming product can be used or released, and the risk to the "
                  "user. Required before a concession is approved.")

    # Design control (7.3.3 to 7.3.5)
    design_element = models.CharField("Design element", max_length=10, blank=True,
                                      choices=wf.DESIGN_ELEMENTS)
    acceptance_criteria = models.TextField(
        "Acceptance criteria", blank=True,
        help_text="The measurable criteria the design must meet, or the requirements it must "
                  "satisfy.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ref} {self.title}"

    @property
    def audit_type(self):
        return "Record"

    @property
    def audit_ref(self):
        return self.ref

    # --- derived values ---------------------------------------------------

    @property
    def type_label(self):
        return dict(wf.RECORD_TYPES)[self.record_type]

    @property
    def is_locked(self):
        return self.status in wf.TERMINAL_STATES

    @property
    def report_due(self):
        """Vigilance report deadline from date aware + deadline category."""
        if self.record_type != wf.INCIDENT or not (self.date_aware and self.deadline_category):
            return None
        days = settings.QMS_VIGILANCE_DEADLINES[self.deadline_category]["days"]
        return self.date_aware + timedelta(days=days)

    @property
    def next_deadline(self):
        if self.is_locked:
            return None
        if self.record_type == wf.INCIDENT and self.status == "assessing":
            return self.report_due
        if self.record_type == wf.CAPA and self.status == "effectiveness_check":
            return self.effectiveness_due
        if self.record_type == wf.PMS_ACTIVITY:
            return self.due_date
        if self.record_type in (wf.INTERNAL_AUDIT, wf.MANAGEMENT_REVIEW) and self.status == "planned":
            return self.planned_date
        return None

    @property
    def is_overdue(self):
        d = self.next_deadline
        return bool(d and d < date.today())

    def state_hash(self) -> str:
        data = {f: getattr(self, f) for f in ["ref", "status"] + AUDITED_FIELDS}
        if self.pk:
            data["hazards"] = sorted(self.hazards.values_list("ref", flat=True))
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

    # --- persistence ------------------------------------------------------

    def _snapshot(self):
        return _readable_snapshot(self, AUDITED_FIELDS)

    def clean(self):
        if self.date_aware and self.date_aware > date.today():
            raise ValidationError({"date_aware": "Date aware cannot be in the future."})

    def save(self, *args, _via_workflow=False, **kwargs):
        from .. import notifications
        creating = self.pk is None
        if creating:
            self.status = wf.initial_state(self.record_type)
            if self.created_by_id is None:
                user = get_current_user()
                if user is not None and user.is_authenticated:
                    self.created_by = user
            with transaction.atomic():
                prefix = wf.REF_PREFIX[self.record_type]
                count = Record.objects.select_for_update().filter(
                    record_type=self.record_type).count()
                self.ref = f"{prefix}-{count + 1:04d}"
                super().save(*args, **kwargs)
                AuditEvent.log("create", record=self,
                               changes={k: [None, v] for k, v in self._snapshot().items()
                                        if v not in ("", None, False)})
                notifications.record_created(self)
            return

        old = Record.objects.get(pk=self.pk)
        if old.status != self.status and not _via_workflow:
            raise ImmutableError("Status can only change through a workflow transition.")
        if old.is_locked and not _via_workflow:
            raise ImmutableError(f"{self.ref} is {old.status} and locked against edits.")
        before, after = old._snapshot(), self._snapshot()
        diff = {k: [before[k], after[k]] for k in before if before[k] != after[k]}
        with transaction.atomic():
            super().save(*args, **kwargs)
            if diff:
                AuditEvent.log("update", record=self, changes=diff)
            if "owner" in diff and self.owner_id:
                notifications.record_assigned(self)

    def delete(self, *args, **kwargs):
        raise ImmutableError("Quality records are never deleted. Reject or close them instead.")


class RecordLink(models.Model):
    LINK_TYPES = [
        ("relates_to", "relates to"),
        ("fixed_by", "is fixed by"),
        ("caused_by", "is caused by"),
        ("escalated_to", "escalated to"),
        ("triggered", "triggered"),
        ("verified_by", "is verified by"),
    ]
    source = models.ForeignKey(Record, on_delete=models.PROTECT, related_name="outgoing_links")
    target = models.ForeignKey(Record, on_delete=models.PROTECT, related_name="incoming_links")
    link_type = models.CharField(max_length=20, choices=LINK_TYPES)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("source", "target", "link_type")]

    def __str__(self):
        return f"{self.source.ref} {self.get_link_type_display()} {self.target.ref}"

    def clean(self):
        if self.source_id == self.target_id:
            raise ValidationError("A record cannot link to itself.")

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating:
            AuditEvent.log("link", record=self.source, actor=self.created_by,
                           changes={"link": [None, str(self)]})

    def delete(self, *args, **kwargs):
        if self.source.is_locked:
            raise ImmutableError("Links on a locked record cannot be removed.")
        AuditEvent.log("unlink", record=self.source, changes={"link": [str(self), None]})
        return super().delete(*args, **kwargs)


# ---------------------------------------------------------------------------
# Electronic signatures
# ---------------------------------------------------------------------------

class Signature(models.Model):
    """An electronic signature: who, when, what it means, and the exact state signed."""
    record = models.ForeignKey(Record, null=True, blank=True, on_delete=models.PROTECT,
                               related_name="signatures")
    object_type = models.CharField(max_length=50, blank=True, db_index=True)
    object_ref = models.CharField(max_length=60, blank=True, db_index=True)
    signer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    signer_name = models.CharField(max_length=200)
    meaning = models.CharField(max_length=100)
    transition = models.CharField(max_length=50, blank=True)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    comment = models.TextField(blank=True)
    record_state_hash = models.CharField("State hash", max_length=64)
    signed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["signed_at"]

    def __str__(self):
        return f"{self.signer_name} – {self.meaning} – {self.signed_at:%Y-%m-%d %H:%M}"

    @property
    def subject(self):
        return self.record.ref if self.record_id else f"{self.object_type} {self.object_ref}"

    @classmethod
    def for_object(cls, obj):
        if isinstance(obj, Record):
            return cls.objects.filter(record=obj)
        return cls.objects.filter(object_type=obj.audit_type, object_ref=obj.audit_ref)

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableError("Signatures cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError("Signatures cannot be deleted.")


class SigningPin(models.Model):
    """
    A separate signing credential. Needed for single sign-on users, who have no local
    password; optional for everyone else. If set, it is used instead of the account password.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="signing_pin")
    pin_hash = models.CharField(max_length=200)
    updated_at = models.DateTimeField(auto_now=True)

    def set_pin(self, raw):
        self.pin_hash = make_password(raw)

    def check_pin(self, raw):
        return check_password(raw, self.pin_hash)


def verify_signing_credential(user, secret: str) -> bool:
    if not secret:
        return False
    pin = SigningPin.objects.filter(user=user).first()
    if pin:
        return pin.check_pin(secret)
    return user.has_usable_password() and user.check_password(secret)


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------

def attachment_path(instance, filename):
    return f"attachments/{timezone.now():%Y/%m}/{instance.sha256[:12]}_{os.path.basename(filename)}"


def sha256_of(django_file) -> str:
    h = hashlib.sha256()
    django_file.seek(0)
    for chunk in django_file.chunks():
        h.update(chunk)
    django_file.seek(0)
    return h.hexdigest()


class Attachment(AuditedModel):
    """Evidence file on a record. Immutable once uploaded; integrity checked by SHA-256."""
    AUDITED = ["record_id", "original_name", "sha256", "size", "description"]

    record = models.ForeignKey(Record, on_delete=models.PROTECT, related_name="attachments")
    file = models.FileField(upload_to=attachment_path)
    original_name = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64, editable=False)
    size = models.PositiveBigIntegerField(editable=False)
    description = models.CharField(max_length=300, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"{self.record.ref}/{self.original_name}"

    def check_editable(self, old, via_workflow):
        if old is not None:
            raise ImmutableError("Attachments cannot be changed after upload.")
        if self.record.is_locked:
            raise ImmutableError(f"{self.record.ref} is locked; files cannot be added.")

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.sha256 = sha256_of(self.file)
            self.size = self.file.size
            self.original_name = self.original_name or os.path.basename(self.file.name)
        super().save(*args, **kwargs)

    def verify(self) -> bool:
        with self.file.open("rb") as f:
            return sha256_of(f) == self.sha256


# ---------------------------------------------------------------------------
# PMS schedules
# ---------------------------------------------------------------------------

class PMSSchedule(models.Model):
    """A recurring post-market surveillance activity for one device."""
    device = models.ForeignKey("Device", on_delete=models.PROTECT, related_name="pms_schedules")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cadence_months = models.PositiveSmallIntegerField(
        help_text="1 = monthly, 3 = quarterly, 6 = 6-monthly, 12 = annual")
    next_due = models.DateField()
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["next_due", "name"]
        verbose_name = "PMS schedule"

    def __str__(self):
        return f"{self.device.code}: {self.name} (every {self.cadence_months} mo)"


def add_months(d: date, months: int) -> date:
    """Add months, keeping month-end dates at month end (31 Jan + 1 month = 28/29 Feb)."""
    import calendar
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    last = calendar.monthrange(y, m)[1]
    day = last if d.day == calendar.monthrange(d.year, d.month)[1] else min(d.day, last)
    return date(y, m, day)
