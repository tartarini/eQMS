import os
from datetime import date

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models, transaction
from django.utils import timezone

from .core import AuditedModel, ImmutableError, add_months, sha256_of
from .devices import TECH_FILE_SECTIONS

DOC_TYPES = [
    ("SOP", "Standard operating procedure"),
    ("WI", "Work instruction"),
    ("POL", "Policy"),
    ("PLAN", "Plan"),
    ("SPEC", "Specification"),
    ("FORM", "Form / template"),
    ("RPT", "Report"),
    ("GAP", "Gap assessment"),
]


class Document(AuditedModel):
    """A controlled document (SOP, plan, policy…). Its content lives in versions."""
    AUDITED = ["title", "doc_type", "device_id", "tech_file_section", "owner_id",
               "review_period_months", "description", "obsolete", "obsolete_on"]

    number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=200)
    doc_type = models.CharField("Type", max_length=10, choices=DOC_TYPES)
    description = models.TextField(blank=True)
    device = models.ForeignKey(
        "Device", null=True, blank=True, on_delete=models.PROTECT, related_name="documents",
        help_text="Leave blank for QMS-wide documents (SOPs, policies) that apply to every device.")
    tech_file_section = models.CharField(
        "Technical file section", max_length=20, blank=True,
        choices=TECH_FILE_SECTIONS,
        help_text="Where this document goes in the device's technical file.")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="owned_documents")
    review_period_months = models.PositiveSmallIntegerField(
        default=24, help_text="How often the effective version must be reviewed.")
    obsolete = models.BooleanField(default=False, editable=False)
    obsolete_on = models.DateField(null=True, blank=True, editable=False,
                                   help_text="Date the document was withdrawn.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"{self.number} {self.title}"

    @property
    def audit_ref(self):
        return self.number

    def check_editable(self, old, via_workflow):
        if old is not None and old.obsolete and not via_workflow:
            raise ImmutableError(f"{self.number} is obsolete and locked.")

    def save(self, *args, **kwargs):
        if self.pk is None:
            with transaction.atomic():
                n = Document.objects.select_for_update().filter(doc_type=self.doc_type).count()
                self.number = f"{self.doc_type}-{n + 1:03d}"
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @property
    def effective_version(self):
        return self.versions.filter(status="effective").first()

    @property
    def open_version(self):
        """The version currently being drafted, reviewed or awaiting effectiveness."""
        return self.versions.filter(status__in=["draft", "in_review", "approved"]).first()

    @property
    def next_review_date(self):
        v = self.effective_version
        return v.next_review_date if v else None

    @property
    def review_overdue(self):
        d = self.next_review_date
        return bool(d and d < date.today())

    def suggest_next_version(self, major=True):
        last = self.versions.order_by("-created_at").first()
        if not last:
            return "1.0"
        try:
            a, b = (int(x) for x in last.version.split(".")[:2])
        except ValueError:
            return ""
        return f"{a + 1}.0" if major else f"{a}.{b + 1}"


def document_path(instance, filename):
    return (f"documents/{instance.document.number}/v{instance.version}/"
            f"{os.path.basename(filename)}")


class DocumentVersion(AuditedModel):
    STATUSES = [("draft", "Draft"), ("in_review", "In review"), ("approved", "Approved"),
                ("effective", "Effective"), ("superseded", "Superseded"),
                ("obsolete", "Obsolete")]
    AUDITED = ["version", "status", "original_name", "sha256", "change_summary",
               "change_request_id", "effective_date", "next_review_date"]
    CONTENT_FIELDS = ["version", "sha256", "change_summary", "change_request_id"]

    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="versions")
    version = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUSES, default="draft", editable=False)
    file = models.FileField(upload_to=document_path, blank=True)
    original_name = models.CharField(max_length=255, blank=True, editable=False)
    sha256 = models.CharField(max_length=64, blank=True, editable=False)
    change_summary = models.TextField(help_text="What changed and why.")
    change_request = models.ForeignKey(
        "Record", null=True, blank=True, on_delete=models.PROTECT,
        limit_choices_to={"record_type": "change_request"}, related_name="document_versions",
        help_text="Change Request that authorised this revision, if any.")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT,
                               related_name="authored_versions")
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    effective_date = models.DateField(null=True, blank=True, editable=False)
    next_review_date = models.DateField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("document", "version")]

    def __str__(self):
        return f"{self.document.number} v{self.version}"

    @property
    def is_editable(self):
        return self.status == "draft"

    def check_editable(self, old, via_workflow):
        if old is None:
            return
        if old.status != self.status and not via_workflow:
            raise ImmutableError("Version status can only change through the review workflow.")
        if old.status != "draft":
            changed = [f for f in self.CONTENT_FIELDS if getattr(old, f) != getattr(self, f)]
            if changed or (self.file and self.file.name != old.file.name):
                raise ImmutableError(
                    f"{self} is {old.get_status_display().lower()}; content is frozen. "
                    "Create a new version instead.")

    def save(self, *args, **kwargs):
        new_upload = self.file and not getattr(self.file, "_committed", True)
        if new_upload:
            self.sha256 = sha256_of(self.file)
            self.original_name = os.path.basename(self.file.name)
        super().save(*args, **kwargs)

    def compute_review_date(self, effective: date):
        return add_months(effective, self.document.review_period_months)

    def verify(self) -> bool:
        if not self.file:
            return False
        with self.file.open("rb") as f:
            return sha256_of(f) == self.sha256


class TrainingRequirement(AuditedModel):
    """Everyone in ``group`` must be trained on each effective version of ``document``."""
    AUDITED = ["document_id", "group_id", "active"]

    document = models.ForeignKey(Document, on_delete=models.PROTECT,
                                 related_name="training_requirements")
    group = models.ForeignKey(Group, on_delete=models.PROTECT, verbose_name="Role")
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("document", "group")]

    def __str__(self):
        return f"{self.document.number} → {self.group.name}"


class TrainingAssignment(AuditedModel):
    AUDITED = ["user_id", "version_id", "due_date", "completed_at"]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name="training")
    version = models.ForeignKey(DocumentVersion, on_delete=models.PROTECT,
                                related_name="training_assignments")
    assigned_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "version")]
        ordering = ["completed_at", "due_date"]

    def __str__(self):
        return f"{self.user.get_username()}: {self.version}"

    def check_editable(self, old, via_workflow):
        if old is not None and old.completed_at and not via_workflow:
            raise ImmutableError("Completed training records cannot be changed.")

    @property
    def status(self):
        if self.completed_at:
            return "completed"
        if self.version.status != "effective":
            return "superseded"
        if self.due_date < date.today():
            return "overdue"
        return "due"


class ReviewReminder(models.Model):
    """A review reminder already sent for one review date at one stage (days before it is
    due, or 0 when due or overdue), so each stage is emailed once."""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="review_reminders")
    review_date = models.DateField()
    stage = models.PositiveSmallIntegerField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("document", "review_date", "stage")]

    def __str__(self):
        return f"{self.document.number} review {self.review_date} stage {self.stage}"

