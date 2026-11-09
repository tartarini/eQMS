"""Account requests: someone who registered with single sign-on asks for access."""
from django.conf import settings
from django.db import models

from .core import AuditedModel, ImmutableError


class AccessRequest(AuditedModel):
    """
    Made from the public landing page. The person passes the captcha, registers with single
    sign-on (Google, Microsoft, LinkedIn or ORCID), then describes who they are and what they
    need. Their account has no role until a Device admin or QA approves the request by putting
    them on a device team, so a request on its own gives no access to QMS data.
    """
    STATUSES = [("unconfirmed", "Email not confirmed"), ("pending", "Waiting for review"),
                ("approved", "Approved"), ("declined", "Declined")]
    OPEN = ("unconfirmed", "pending")
    AUDITED = ["user_id", "first_name", "last_name", "email", "email_verified", "organisation",
               "position", "devices", "role", "reason", "provider", "status", "grants",
               "decision_note", "decided_by_id"]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name="access_requests")
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField()
    email_verified = models.BooleanField(default=False)
    organisation = models.CharField(max_length=200)
    position = models.CharField(max_length=200)
    devices = models.CharField(max_length=300)
    role = models.CharField(max_length=40)
    reason = models.TextField()
    provider = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default="unconfirmed")
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="access_decisions")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    # [{"device_id": 3, "device": "SKN", "roles": ["Engineer"]}] once approved
    grants = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ref} from {self.full_name}"

    @property
    def ref(self):
        return f"AR-{self.pk:04d}" if self.pk else "AR-new"

    @property
    def audit_ref(self):
        return self.ref

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN

    def check_editable(self, old, via_workflow):
        if old is not None and old.status not in self.OPEN:
            raise ImmutableError(f"{old.ref} is {old.status} and can't be changed.")
