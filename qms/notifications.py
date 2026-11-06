"""
Email notifications. Messages are sent after the database transaction commits, so nobody is
told about a change that was rolled back. Delivery failures are logged, never raised.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse

from . import workflow as wf

log = logging.getLogger(__name__)


def _url(path: str) -> str:
    return settings.QMS_BASE_URL.rstrip("/") + path


def users_in_roles(roles, device=None):
    """Active users in any of the roles; limited to the device's team when a device is given."""
    from .services import _team_filter
    User = get_user_model()
    users = User.objects.filter(is_active=True, groups__name__in=roles).distinct()
    return _team_filter(users, device)


def _emails(users):
    return sorted({u.email for u in users if u.email and u.is_active})


def send(subject: str, body: str, users) -> None:
    recipients = _emails(users)
    if not recipients or not settings.QMS_NOTIFICATIONS_ENABLED:
        return

    def _send():
        try:
            send_mail(f"[SAMD_QMS] {subject}", body, settings.DEFAULT_FROM_EMAIL, recipients)
        except Exception:  # noqa: BLE001 - never break a workflow because email failed
            log.exception("Failed to send notification %r to %s", subject, recipients)

    transaction.on_commit(_send)


# --- events -------------------------------------------------------------------

def record_created(record):
    if record.record_type == wf.INCIDENT:
        send(f"URGENT: new {record.device.code} incident {record.ref}",
             f"A possibly reportable incident has been opened: {record.title}\n\n"
             "Check the reporting deadline as soon as the date aware and category are set.\n\n"
             + _url(reverse("qms:record_detail", args=[record.ref])),
             users_in_roles([wf.QA, wf.CLINICAL_SAFETY], record.device))
    elif record.record_type == wf.COMPLAINT:
        send(f"New {record.device.code} complaint {record.ref}",
             f"{record.title}\n\n" + _url(reverse("qms:record_detail", args=[record.ref])),
             users_in_roles([wf.QA], record.device))


def record_assigned(record):
    if record.owner:
        send(f"{record.device.code} {record.ref} assigned to you",
             f"You are now the owner of {record.type_label} {record.ref}: {record.title}\n\n"
             + _url(reverse("qms:record_detail", args=[record.ref])),
             [record.owner])


def record_transitioned(record, actor):
    """Tell the people who can take the next step, when it is restricted to specific roles."""
    roles = set()
    for t in wf.all_transitions(record.record_type):
        if record.status in t.sources and set(t.roles) != set(wf.ANY_ROLE):
            roles.update(t.roles)
    recipients = ([u for u in users_in_roles(roles, record.device) if u.pk != actor.pk]
                  if roles else [])
    if record.owner and record.owner.pk != actor.pk:
        recipients.append(record.owner)
    send(f"{record.device.code} {record.ref} is now {record.get_status_display().lower()}",
         f"{record.type_label} {record.ref}: {record.title}\n"
         f"Moved to '{record.get_status_display()}' by {actor.get_username()}.\n\n"
         + _url(reverse("qms:record_detail", args=[record.ref])),
         recipients)


def document_submitted(version):
    send(f"{version} ready for review",
         f"{version.document.title} v{version.version} has been submitted for review.\n\n"
         f"Change: {version.change_summary}\n\n"
         + _url(reverse("qms:document_detail", args=[version.document.number])),
         users_in_roles([wf.QA], version.document.device))


def document_effective(version):
    if version.document.owner:
        send(f"{version} is now effective",
             f"{version.document.title} v{version.version} became effective on "
             f"{version.effective_date:%d %b %Y}. Next review: {version.next_review_date:%d %b %Y}.",
             [version.document.owner])


def training_assigned(assignment):
    send(f"Training: read {assignment.version}",
         f"Please read and sign off {assignment.version.document.title} "
         f"v{assignment.version.version} by {assignment.due_date:%d %b %Y}.\n\n"
         + _url(reverse("qms:my_training")),
         [assignment.user])


def user_awaiting_access(user):
    User = get_user_model()
    admins = list(users_in_roles([wf.QA])) + list(User.objects.filter(is_superuser=True,
                                                                      is_active=True))
    send(f"New user awaiting access: {user.get_username()}",
         f"{user.get_full_name() or user.get_username()} ({user.email or 'no email'}) signed in "
         "with single sign-on and has no QMS role yet. Assign a role in the admin if they "
         "should have access.\n\n" + _url(reverse("admin:auth_user_change", args=[user.pk])),
         admins)


def daily_reminders():
    """Overdue and due-soon items, one email per person. Returns the number of emails queued."""
    from datetime import date, timedelta

    from .models import Document, Record, SoupItem, Supplier, TrainingAssignment

    today = date.today()
    soon = today + timedelta(days=settings.QMS_REMINDER_LOOKAHEAD_DAYS)
    open_records = [r for r in Record.objects.exclude(status__in=wf.TERMINAL_STATES)
                    if r.next_deadline and r.next_deadline <= soon]

    lines_by_user = {}

    def add(user, line):
        lines_by_user.setdefault(user, []).append(line)

    for r in open_records:
        when = "OVERDUE" if r.next_deadline < today else "due"
        line = f"[{r.device.code}] {r.ref} {r.title} – {when} {r.next_deadline:%d %b %Y}"
        if r.owner:
            add(r.owner, line)
        for u in users_in_roles([wf.QA], r.device):
            add(u, line)

    for a in TrainingAssignment.objects.filter(completed_at__isnull=True, due_date__lte=soon,
                                               version__status="effective"):
        when = "OVERDUE" if a.due_date < today else "due"
        add(a.user, f"Training: {a.version} – {when} {a.due_date:%d %b %Y}")

    qa = list(users_in_roles([wf.QA]))
    for d in Document.objects.filter(obsolete=False):
        if d.next_review_date and d.next_review_date <= soon:
            line = f"Document review: {d} – {d.next_review_date:%d %b %Y}"
            for u in list(users_in_roles([wf.QA], d.device)) + ([d.owner] if d.owner else []):
                add(u, line)
    for s in Supplier.objects.exclude(status="disqualified"):
        if s.evaluation_overdue:
            for u in qa:
                add(u, f"Supplier evaluation overdue: {s.name}")
    for u in qa:
        from .access import accessible_devices
        visible = accessible_devices(u)
        stale = [s for s in SoupItem.objects.filter(active=True).prefetch_related("devices")
                 if s.review_overdue and (not s.devices.exists()
                                          or s.devices.filter(pk__in=visible).exists())]
        if stale:
            add(u, f"SOUP anomaly review overdue for {len(stale)} item(s)")

    for user, lines in lines_by_user.items():
        unique = list(dict.fromkeys(lines))
        send(f"{len(unique)} item(s) need attention",
             "\n".join(f"- {x}" for x in unique) + "\n\n" + _url(reverse("qms:dashboard")),
             [user])
    return len(lines_by_user)
