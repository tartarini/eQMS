"""Invitations: an email address, the roles to grant on one or more devices, and an expiry."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from .core import AuditedModel, ImmutableError


class Invitation(AuditedModel):
    """
    Sent by a Device admin or QA to an email address. The link carries a random token; only
    its SHA-256 is stored. Accepting it (once, before it expires) puts the person on each
    device's team with the roles granted there.
    """
    STATUSES = [("pending", "Pending"), ("accepted", "Accepted"), ("revoked", "Revoked")]
    AUDITED = ["email", "grants", "status", "expires_at", "message", "accepted_by_id"]

    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    # [{"device_id": 3, "device": "SKN", "roles": ["Engineer", "QA"]}, ...]
    grants = models.JSONField(default=list)
    message = models.TextField(blank=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="invitations_sent")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default="pending")
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="invitations_accepted")
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ref} to {self.email}"

    @property
    def ref(self):
        return f"INV-{self.pk:04d}" if self.pk else "INV-new"

    @property
    def audit_ref(self):
        return self.ref

    @property
    def is_expired(self) -> bool:
        return self.status == "pending" and self.expires_at <= timezone.now()

    @property
    def state(self) -> str:
        """pending, expired, accepted or revoked."""
        return "expired" if self.is_expired else self.status

    def state_label(self) -> str:
        return {"pending": "Pending", "expired": "Expired", "accepted": "Accepted",
                "revoked": "Revoked"}[self.state]

    def device_ids(self) -> list:
        return [g["device_id"] for g in self.grants]

    def grant_lines(self) -> list:
        """(device code, "Engineer, QA") for display."""
        return [(g["device"], ", ".join(g["roles"])) for g in self.grants]

    def check_editable(self, old, via_workflow):
        if old is not None and old.status != "pending":
            raise ImmutableError(f"{old.ref} is {old.status} and can't be changed.")
