from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """One message to one person, or to an address with no account.

    Kept until it is sent, so a failed email is retried, and kept afterwards, so each person can
    see what they were told in their inbox. It is not part of the audit trail: the records and
    signatures it points to are what is audited.
    """
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    STATUSES = [(PENDING, "Waiting to send"), (SENT, "Sent"), (FAILED, "Could not send")]
    MAX_ATTEMPTS = 5

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.CASCADE, related_name="notifications")
    email = models.EmailField(max_length=254)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    # Where the inbox takes the person: a path inside the app, e.g. /records/PR-0002/.
    path = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["recipient", "read_at"], name="notif_inbox_idx"),
                   models.Index(fields=["status"], name="notif_status_idx")]

    def __str__(self):
        return f"{self.subject} to {self.email}"
