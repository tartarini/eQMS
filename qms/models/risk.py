"""Risk management (ISO 14971): hazard register, risk controls and acceptance."""
from django.conf import settings
from django.db import models, transaction

from .core import AuditedModel, ImmutableError

SEVERITY_SCALE = [(1, "1 Negligible"), (2, "2 Minor"), (3, "3 Serious"), (4, "4 Critical"),
                  (5, "5 Catastrophic")]
PROBABILITY_SCALE = [(1, "1 Improbable"), (2, "2 Remote"), (3, "3 Occasional"),
                     (4, "4 Probable"), (5, "5 Frequent")]
LEVEL_LABELS = {"acceptable": "Acceptable", "alarp": "Reduce as far as possible",
                "unacceptable": "Unacceptable"}


def risk_level(severity, probability):
    """Acceptability from the risk matrix. Thresholds are set in settings."""
    if not (severity and probability):
        return None
    score = severity * probability
    if score <= settings.QMS_RISK_ACCEPTABLE_MAX:
        return "acceptable"
    if score >= settings.QMS_RISK_UNACCEPTABLE_MIN:
        return "unacceptable"
    return "alarp"


class Hazard(AuditedModel):
    STATUSES = [("open", "Open"), ("accepted", "Accepted"), ("retired", "Retired")]
    AUDITED = ["device_id", "title", "hazard", "hazardous_situation", "harm", "cause", "software_item",
               "owner_id", "severity_initial", "probability_initial", "severity_residual",
               "probability_residual", "benefit_risk_rationale", "status"]

    ref = models.CharField(max_length=20, unique=True, editable=False)
    device = models.ForeignKey("Device", on_delete=models.PROTECT, related_name="hazards")
    title = models.CharField(max_length=200)
    hazard = models.TextField(help_text="Potential source of harm.")
    cause = models.TextField("Sequence of events / cause", blank=True)
    hazardous_situation = models.TextField(blank=True)
    harm = models.TextField(help_text="Injury or damage to health, e.g. delayed diagnosis.")
    software_item = models.CharField(max_length=100, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="owned_hazards")
    severity_initial = models.PositiveSmallIntegerField("Severity (before controls)",
                                                        choices=SEVERITY_SCALE)
    probability_initial = models.PositiveSmallIntegerField("Probability (before controls)",
                                                           choices=PROBABILITY_SCALE)
    severity_residual = models.PositiveSmallIntegerField("Severity (residual)",
                                                         choices=SEVERITY_SCALE, null=True,
                                                         blank=True)
    probability_residual = models.PositiveSmallIntegerField("Probability (residual)",
                                                            choices=PROBABILITY_SCALE, null=True,
                                                            blank=True)
    benefit_risk_rationale = models.TextField(
        blank=True, help_text="Required to accept a residual risk that is not acceptable "
                              "by the matrix.")
    status = models.CharField(max_length=20, choices=STATUSES, default="open", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ref"]

    def __str__(self):
        return f"{self.ref} {self.title}"

    @property
    def audit_ref(self):
        return self.ref

    @property
    def is_locked(self):
        return self.status != "open"

    def check_editable(self, old, via_workflow):
        if old is None or via_workflow:
            return
        if old.status != self.status:
            raise ImmutableError("Hazard status changes only by acceptance, reopening or retiring.")
        if old.is_locked:
            raise ImmutableError(f"{self.ref} is {old.status}; reopen it to make changes.")

    def save(self, *args, **kwargs):
        if self.pk is None:
            with transaction.atomic():
                n = Hazard.objects.select_for_update().count()
                self.ref = f"HAZ-{n + 1:03d}"
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @property
    def initial_level(self):
        return risk_level(self.severity_initial, self.probability_initial)

    @property
    def residual_level(self):
        return risk_level(self.severity_residual, self.probability_residual)

    @property
    def initial_level_label(self):
        return LEVEL_LABELS.get(self.initial_level, "")

    @property
    def residual_level_label(self):
        return LEVEL_LABELS.get(self.residual_level, "")

    @property
    def initial_score(self):
        return self.severity_initial * self.probability_initial

    @property
    def residual_score(self):
        if self.severity_residual and self.probability_residual:
            return self.severity_residual * self.probability_residual
        return None


class RiskControl(AuditedModel):
    CONTROL_TYPES = [("design", "Inherent safety by design"),
                     ("protective", "Protective measure"),
                     ("information", "Information for safety")]
    AUDITED = ["description", "control_type", "implemented_by_id", "verification_evidence",
               "verified"]

    hazard = models.ForeignKey(Hazard, on_delete=models.PROTECT, related_name="controls")
    description = models.TextField()
    control_type = models.CharField(max_length=20, choices=CONTROL_TYPES)
    implemented_by = models.ForeignKey(
        "Record", null=True, blank=True, on_delete=models.PROTECT,
        limit_choices_to={"record_type": "change_request"}, related_name="risk_controls",
        help_text="Change Request implementing this control.")
    verification_evidence = models.CharField(max_length=300, blank=True,
                                             help_text="Test, review or report showing it works.")
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.hazard.ref} control: {self.description[:40]}"

    @property
    def audit_ref(self):
        return f"{self.hazard.ref}/RC-{self.pk}"

    def check_editable(self, old, via_workflow):
        if self.hazard.is_locked and not via_workflow:
            raise ImmutableError(f"{self.hazard.ref} is {self.hazard.status}; reopen it first.")
        if self.verified and not self.verification_evidence:
            raise ImmutableError("A control can only be marked verified with evidence.")
