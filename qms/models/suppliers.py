"""Supplier control (ISO 13485 §7.4) and the SOUP list (IEC 62304 §8.1.2)."""
from datetime import date, timedelta

from django.conf import settings
from django.db import models

from .core import AuditedModel, ImmutableError, add_months


class Supplier(AuditedModel):
    CATEGORIES = [("soup", "SOUP / open-source"), ("cloud", "Cloud / hosting"),
                  ("service", "Service"), ("data", "Data / clinical"), ("other", "Other")]
    CRITICALITY = [("high", "High"), ("medium", "Medium"), ("low", "Low")]
    STATUSES = [("proposed", "Proposed"), ("approved", "Approved"),
                ("conditional", "Conditionally approved"), ("disqualified", "Disqualified")]
    AUDITED = ["name", "category", "criticality", "scope", "contact", "status",
               "last_evaluated", "evaluation_interval_months", "notes"]

    name = models.CharField(max_length=200, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    criticality = models.CharField(max_length=10, choices=CRITICALITY,
                                   help_text="Impact on device safety and performance.")
    scope = models.TextField(help_text="What they supply and how it is used.")
    contact = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default="proposed",
                              editable=False)
    last_evaluated = models.DateField(null=True, blank=True, editable=False)
    evaluation_interval_months = models.PositiveSmallIntegerField(default=12)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def check_editable(self, old, via_workflow):
        if old is not None and old.status != self.status and not via_workflow:
            raise ImmutableError("Supplier status changes only through a signed evaluation.")

    @property
    def next_evaluation(self):
        if not self.last_evaluated:
            return None
        return add_months(self.last_evaluated, self.evaluation_interval_months)

    @property
    def evaluation_overdue(self):
        if self.status == "disqualified":
            return False
        d = self.next_evaluation
        return d is None or d < date.today()


class SoupItem(AuditedModel):
    SAFETY_CLASSES = [("A", "Class A"), ("B", "Class B"), ("C", "Class C")]
    AUDITED = ["name", "version", "supplier_id", "software_item", "purpose", "licence",
               "safety_class", "known_anomalies", "last_anomaly_review", "active"]

    name = models.CharField(max_length=200)
    version = models.CharField(max_length=50)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name="soup_items")
    devices = models.ManyToManyField("Device", blank=True, related_name="soup_items",
                                     help_text="Devices whose software includes this item.")
    software_item = models.CharField(max_length=100, blank=True)
    purpose = models.TextField(help_text="Functional and performance requirements it meets.")
    licence = models.CharField(max_length=100, blank=True)
    safety_class = models.CharField("Software safety class", max_length=1,
                                    choices=SAFETY_CLASSES, blank=True)
    known_anomalies = models.TextField(
        blank=True, help_text="Published anomalies and vulnerabilities reviewed, and their impact.")
    last_anomaly_review = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "version"]
        unique_together = [("name", "version")]
        verbose_name = "SOUP item"

    def __str__(self):
        return f"{self.name} {self.version}"

    @property
    def review_overdue(self):
        if not self.active:
            return False
        if not self.last_anomaly_review:
            return True
        return self.last_anomaly_review < date.today() - timedelta(
            days=settings.QMS_SOUP_REVIEW_DAYS)
