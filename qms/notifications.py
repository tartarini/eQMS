"""
Notifications. Every message is first stored as a ``Notification`` in the same transaction as
the change that caused it, so a rolled-back change tells nobody, and a message that can't be sent
is kept and tried again. Each person also sees their notifications in the inbox.

Sending happens after the transaction commits, and delivery failures are logged, never raised.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from . import workflow as wf
from .models import Notification

log = logging.getLogger(__name__)


def _url(path: str) -> str:
    return settings.QMS_BASE_URL.rstrip("/") + path


def users_in_roles(roles, device=None):
    """Active people holding any of the roles on the device (anywhere when device is None)."""
    from .roles import users_with_roles
    return users_with_roles(roles, device)


def _people(users) -> dict:
    """{address: user} for the active people with an address; one message per address."""
    found = {}
    for u in users:
        if u.email and u.is_active:
            found.setdefault(u.email, u)
    return found


def _queue(subject: str, body: str, recipients: dict, path: str = "") -> None:
    """Store one notification per address, then send them after the transaction commits.

    ``recipients`` maps each address to its account, or to None for an address with no account
    (those get email only, not an inbox entry). ``path`` is the page the message is about: it
    is linked from the email and opened from the inbox.
    """
    if not recipients or not settings.QMS_NOTIFICATIONS_ENABLED:
        return
    text = body.rstrip() + (f"\n\n{_url(path)}" if path else "")
    Notification.objects.bulk_create([
        Notification(recipient=user, email=address, subject=subject, body=text, path=path)
        for address, user in sorted(recipients.items())])
    transaction.on_commit(_dispatch_after_commit)


def send(subject: str, body: str, users, path: str = "") -> None:
    """A message to these people, with a link to ``path`` in the app."""
    _queue(subject, body, _people(users), path)


def send_to(subject: str, body: str, recipients) -> None:
    """A message to email addresses, which may have no account (so no inbox entry)."""
    _queue(subject, body, {address: None for address in recipients})


# --- delivery -----------------------------------------------------------------

def _dispatch_after_commit():
    try:
        dispatch_pending()
    except Exception:  # noqa: BLE001 - the scheduler sends what is left
        log.exception("Could not send queued notifications")


def dispatch_pending(limit: int = 500) -> int:
    """Send the queued notifications. A failed send is tried again on the next run; after
    ``Notification.MAX_ATTEMPTS`` it is marked failed. Returns how many were sent."""
    sent = 0
    waiting = (Notification.objects.filter(status=Notification.PENDING)
               .order_by("created_at", "pk").values_list("pk", flat=True)[:limit])
    for pk in list(waiting):
        with transaction.atomic():
            # Locked, so two runs (a commit and the scheduler) never send the same message twice.
            n = (Notification.objects.select_for_update(skip_locked=True)
                 .filter(pk=pk, status=Notification.PENDING).first())
            if n is None:
                continue
            n.attempts += 1
            try:
                send_mail(f"[{settings.QMS_PRODUCT_NAME}] {n.subject}", n.body, settings.DEFAULT_FROM_EMAIL,
                          [n.email])
            except Exception as exc:  # noqa: BLE001 - keep the message and try again later
                n.last_error = str(exc)[:500]
                n.status = (Notification.FAILED if n.attempts >= Notification.MAX_ATTEMPTS
                            else Notification.PENDING)
                log.exception("Failed to send notification %r to %s (attempt %s)",
                              n.subject, n.email, n.attempts)
            else:
                n.status = Notification.SENT
                n.sent_at = timezone.now()
                n.last_error = ""
                sent += 1
            n.save(update_fields=["status", "attempts", "last_error", "sent_at"])
    return sent


# --- events -------------------------------------------------------------------

def record_created(record):
    if record.record_type == wf.INCIDENT:
        send(f"URGENT: new {record.device.code} incident {record.ref}",
             f"A possibly reportable incident has been opened: {record.title}\n\n"
             "Check the reporting deadline as soon as the date aware and category are set.",
             users_in_roles([wf.QA, wf.CLINICAL_SAFETY], record.device),
             path=reverse("qms:record_detail", args=[record.ref]))
    elif record.record_type == wf.COMPLAINT:
        send(f"New {record.device.code} complaint {record.ref}",
             f"{record.title}",
             users_in_roles([wf.QA], record.device),
             path=reverse("qms:record_detail", args=[record.ref]))


def gate_open(gate):
    """Tell the approver of a stage gate that it is now their turn, and alert them to any gate
    checks that don't pass yet (the gate can't be signed until they do)."""
    from . import doc_route  # avoids a circular import: doc_route -> models -> notifications
    failing = doc_route.gate_check_failures(gate.device, gate.stage)
    alert = ("" if not failing else
             "It can't be signed yet: these gate checks don't pass:\n"
             + "".join(f"- {label}\n" for label in failing)
             + "Fix them on the device page, then sign.\n\n")
    send(f"{gate.device.code} Stage {gate.stage} ready for approval"
         + (" (gate checks not passing)" if failing else ""),
         f"Stage {gate.stage}: {gate.name} ({gate.route.capitalize()} route) is open for "
         f"approval by {gate.approver_role} on {gate.device.name}. The earlier stages are "
         "approved.\n\n" + alert,
         users_in_roles([gate.approver_role], gate.device),
         path=reverse("qms:device_tasks", args=[gate.device.code]))


def record_assigned(record):
    if record.owner:
        send(f"{record.device.code} {record.ref} assigned to you",
             f"You are now the owner of {record.type_label} {record.ref}: {record.title}",
             [record.owner],
             path=reverse("qms:record_detail", args=[record.ref]))


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
         f"Moved to '{record.get_status_display()}' by {actor.get_username()}.",
         recipients,
         path=reverse("qms:record_detail", args=[record.ref]))


def document_submitted(version):
    send(f"{version} ready for review",
         f"{version.document.title} v{version.version} has been submitted for review.\n\n"
         f"Change: {version.change_summary}",
         users_in_roles([wf.QA], version.document.device),
         path=reverse("qms:document_detail", args=[version.document.number]))


def document_approved(version, actor):
    """A version is approved and waits for QA to make it effective."""
    send(f"{version} approved, ready to become effective",
         f"{version.document.title} v{version.version} was approved by {actor.get_username()} "
         "and needs to be made effective.",
         [u for u in users_in_roles([wf.QA], version.document.device) if u.pk != actor.pk],
         path=reverse("qms:document_detail", args=[version.document.number]))


def techfile_ready(build):
    """A technical file build is generated and waits for the QA signature."""
    send(f"{build.device.code} technical file {build.label} needs approval",
         f"Technical file build {build.label} was generated and needs QA approval.",
         users_in_roles([wf.QA], build.device),
         path=reverse("qms:device_tasks", args=[build.device.code]))


def document_effective(version):
    if version.document.owner:
        send(f"{version} is now effective",
             f"{version.document.title} v{version.version} became effective on "
             f"{version.effective_date:%d %b %Y}. Next review: {version.next_review_date:%d %b %Y}.",
             [version.document.owner],
             path=reverse("qms:document_detail", args=[version.document.number]))


def training_assigned(assignment):
    send(f"Training: read {assignment.version}",
         f"Please read and sign off {assignment.version.document.title} "
         f"v{assignment.version.version} by {assignment.due_date:%d %b %Y}.",
         [assignment.user],
         path=reverse("qms:my_training"))


def user_awaiting_access(user):
    User = get_user_model()
    admins = list(users_in_roles([wf.QA])) + list(User.objects.filter(is_superuser=True,
                                                                      is_active=True))
    send(f"New user awaiting access: {user.get_username()}",
         f"{user.get_full_name() or user.get_username()} ({user.email or 'no email'}) signed in "
         "with single sign-on and has no QMS role yet. Assign a role in the admin if they "
         "should have access.",
         admins,
         path=reverse("admin:auth_user_change", args=[user.pk]))


def review_reminders() -> int:
    """Email the owner and device QA once per stage before each document review is due, and
    once when it is due or overdue. Returns the number of emails queued."""
    from datetime import date

    from .models import Document, ReviewReminder

    today = date.today()
    sent = 0
    for doc in Document.objects.filter(obsolete=False).select_related("device", "owner"):
        due = doc.next_review_date
        if not due:
            continue
        days_left = (due - today).days
        stages = [n for n in settings.QMS_REVIEW_REMINDER_DAYS if days_left <= n]
        if not stages:
            continue
        stage = min(stages)
        _, new = ReviewReminder.objects.get_or_create(document=doc, review_date=due, stage=stage)
        if not new:
            continue
        if days_left < 0:
            when = f"was due on {due:%d %b %Y} and is overdue"
        elif days_left == 0:
            when = "is due today"
        else:
            when = f"is due on {due:%d %b %Y} (in {days_left} days)"
        body = (f"{doc.number} {doc.title} {when}.\n\nThe owner and QA need to review it, "
                "then either confirm it still applies or start a new version.")
        recipients = list(users_in_roles([wf.QA], doc.device))
        if doc.owner:
            recipients.append(doc.owner)
        send(f"Document review {'overdue' if days_left < 0 else 'due'}: {doc.number}",
             body, recipients,
             path=reverse("qms:document_detail", args=[doc.number]))
        sent += 1
    return sent


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
             "\n".join(f"- {x}" for x in unique),
             [user],
             path=reverse("qms:dashboard"))
    return len(lines_by_user)


def invitation(inv, link: str):
    """The invitation email, to an address that may not have an account yet."""
    from .models import Device
    inviter = inv.invited_by.get_full_name() or inv.invited_by.get_username()
    lines = "\n".join(f"  - {Device.objects.get(pk=g['device_id']).name} ({g['device']}): "
                      f"{', '.join(g['roles'])}" for g in inv.grants)
    note = f"\nMessage from {inviter}:\n{inv.message}\n" if inv.message else ""
    send_to(f"Invitation to {settings.QMS_PRODUCT_NAME}",
            f"{inviter} has invited you to {settings.QMS_PRODUCT_NAME}, the quality management system for these "
            f"medical devices, with these roles:\n\n{lines}\n{note}\n"
            f"Accept by {inv.expires_at:%d %b %Y %H:%M} UTC, using this link:\n{link}\n\n"
            "Open the link and continue with Google, Microsoft, LinkedIn or GitHub using this "
            "email address; your account is created from it, with no separate password. If you "
            "already have an account, sign in instead. The link works once and expires "
            "automatically.\n\n"
            "If you weren't expecting this email, you can ignore it.",
            [inv.email])


# --- account requests ------------------------------------------------------------

def access_confirm_email(ar, link: str):
    send_to("Confirm your email address",
            f"Hello {ar.first_name},\n\nYou asked for an account on {settings.QMS_PRODUCT_NAME} ({ar.ref}). Confirm "
            f"this email address so that QA can review your request:\n{link}\n\n"
            f"The link expires in {settings.QMS_ACCESS_CONFIRM_DAYS} days. If you didn't ask "
            "for an account, ignore this email.", [ar.email])


def access_requested(ar):
    """To QA and everyone who manages a device team: a request is waiting for review."""
    User = get_user_model()
    people = (set(users_in_roles(wf.TEAM_MANAGERS))
              | set(User.objects.filter(is_superuser=True, is_active=True)))
    people.discard(ar.user)
    send(f"Account request {ar.ref}: {ar.full_name}",
         f"{ar.full_name} ({ar.email}), {ar.position} at {ar.organisation}, asks for access as "
         f"{ar.role}.\n\nDevices or projects: {ar.devices}\n\nReason:\n{ar.reason}\n\n"
         f"Signed up with: {ar.provider or 'single sign-on'}\n\n"
         "Approve by adding them to a device team you manage, or decline (QA):",
         people,
         path=reverse("qms:access_request_list"))


def access_decided(ar):
    if ar.status == "approved":
        lines = "\n".join(f"  - {g['device']}: {', '.join(g['roles'])}" for g in ar.grants)
        body = (f"Hello {ar.first_name},\n\nYour {settings.QMS_PRODUCT_NAME} account request {ar.ref} was approved. "
                f"You're now on these device teams:\n\n{lines}\n\nSign in here:\n"
                + _url(reverse("login")))
    else:
        body = (f"Hello {ar.first_name},\n\nYour {settings.QMS_PRODUCT_NAME} account request {ar.ref} was declined."
                f"\n\nReason: {ar.decision_note}\n\nIf you think this is a mistake, contact the "
                "quality team of the organisation you applied to.")
    send_to(f"Your account request {ar.ref}", body, [ar.email])
