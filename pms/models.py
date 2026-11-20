"""Post-market surveillance: what users report about a device once it is in use.

Three kinds of intake share one record type: feedback (an opinion or a suggestion), complaint
(a dissatisfaction with a device, its labelling or its service) and vigilance (a suspected
incident or malfunction, which may have to be reported to the regulator). Reports are QMS
records: every change to a report is written to the audit trail.
"""
from django.conf import settings
from django.db import models, transaction

from qms.models import AuditedModel, Device


class PmsProfile(models.Model):
    """What kind of end user an account is. QMS staff have no profile: their QMS roles are
    what they use."""
    USER_TYPES = [
        ("clinician", "Clinician"),
        ("patient", "Patient"),
        ("carer", "Carer or family member"),
        ("other", "Other end user"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="pms_profile")
    user_type = models.CharField("I am a", max_length=20, choices=USER_TYPES)
    organisation = models.CharField(
        "Hospital, clinic or organisation", max_length=120, blank=True,
        help_text="Where you use the device, if that applies to you.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_user_type_display()})"


class Report(AuditedModel):
    KINDS = [
        ("feedback", "Feedback"),
        ("complaint", "Complaint"),
        ("vigilance", "Suspected incident or malfunction"),
    ]
    STATUSES = [
        ("new", "New"),
        ("triaged", "Triaged"),
        ("investigating", "Under investigation"),
        ("closed", "Closed"),
    ]
    HARM = [
        ("none", "No harm"),
        ("minor", "Minor harm or inconvenience"),
        ("serious", "Serious deterioration in health"),
        ("death", "Death"),
        ("unknown", "Not known"),
    ]
    AUDITED = ["number", "kind", "device_id", "reporter_id", "reporter_type", "title",
               "description", "occurred_on", "aware_on", "software_version", "environment", "steps",
               "harm", "contact_ok", "status"]

    number = models.CharField(max_length=20, unique=True, editable=False)
    kind = models.CharField(max_length=20, choices=KINDS)
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="pms_reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name="pms_reports")
    reporter_type = models.CharField(
        max_length=20, editable=False,
        help_text="The reporter's kind when they reported: a PmsProfile type, or qms_staff.")
    title = models.CharField(max_length=200)
    description = models.TextField()
    occurred_on = models.DateField(
        null=True, blank=True, verbose_name="Date it happened",
        help_text="The date the problem happened or was first noticed.")
    aware_on = models.DateField(
        null=True, blank=True, verbose_name="Date we became aware",
        help_text="For a suspected incident: the date the manufacturer first knew of it. "
                  "The reporting clock runs from this date.")
    software_version = models.CharField(
        max_length=60, blank=True,
        help_text="The version shown in the app or on its label, if you know it.")
    environment = models.CharField(
        max_length=160, blank=True,
        help_text="Where and how it happened: phone or computer, operating system, browser, "
                  "care setting.")
    steps = models.TextField(
        blank=True, verbose_name="What you did, step by step",
        help_text="The steps that led to the problem, if you can list them.")
    harm = models.CharField(
        max_length=10, choices=HARM, blank=True,
        help_text="What happened to a patient, as far as you know.")
    contact_ok = models.BooleanField(
        default=False, verbose_name="The manufacturer may contact me about this",
        help_text="If not ticked, we will not contact you about this report.")
    status = models.CharField(max_length=20, choices=STATUSES, default="new", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} {self.title}"

    @property
    def audit_ref(self):
        return self.number

    @property
    def is_vigilance(self):
        return self.kind == "vigilance"

    def reporting_deadlines(self):
        """Latest dates for reporting a serious incident, counted from the date of awareness,
        from settings.QMS_VIGILANCE_DEADLINES. Empty unless this is a vigilance report with an
        awareness date. Verify the periods against current guidance before relying on them."""
        from datetime import timedelta
        from django.conf import settings
        if not (self.is_vigilance and self.aware_on):
            return []
        return [(v["label"], self.aware_on + timedelta(days=v["days"]))
                for v in settings.QMS_VIGILANCE_DEADLINES.values()]

    def save(self, *args, **kwargs):
        if self.pk is None:
            with transaction.atomic():
                n = Report.objects.select_for_update().count()
                self.number = f"PMS-{n + 1:05d}"
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)


class ExternalIssue(models.Model):
    """A bug or issue in an external tracker (GitHub, GitLab, Jira...) that a report relates to."""
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="external_issues")
    url = models.URLField(max_length=500, verbose_name="Link to the issue")
    provider = models.CharField(max_length=20)
    reference = models.CharField(max_length=200, blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name="+")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at"]
        unique_together = [("report", "url")]

    @property
    def provider_label(self):
        from .links import PROVIDER_LABELS
        return PROVIDER_LABELS.get(self.provider, self.provider)

    def __str__(self):
        return f"{self.report.number} → {self.url}"
