"""A person's task board for one device: what they have to do, and what they are waiting on.

Nothing is stored. The board is worked out each time from the records, document versions,
technical file builds and training assignments on the device, and from the roles the person
holds on it, so it cannot drift from the workflow. Columns:

- **To do:** an action only this person's roles can take now.
- **Waiting on others:** work they started or own that needs another role to act.
- **Done recently:** electronic signatures they made on this device in the last 30 days.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from . import doc_route, notifications
from . import workflow as wf
from . import services
from .models import (GATES_BY_ROUTE, DocumentVersion, Record, Signature, StageGate,
                     TechnicalFileBuild, TrainingAssignment)
from .roles import device_roles
from .services import TransitionError

RECENT_DAYS = 30


@dataclass(frozen=True)
class Task:
    kind: str
    title: str
    detail: str
    url: str


def ensure_gates(device) -> list:
    """The device's approver gates for its documentation route, created on first use. The
    first gate's approver is told when the gates are first created."""
    created = []
    for stage, name, role in GATES_BY_ROUTE[device.development_route]:
        _, new = StageGate.objects.get_or_create(
            device=device, route=device.development_route, stage=stage,
            defaults={"name": name, "approver_role": role})
        if new:
            created.append(stage)
    gates = list(StageGate.objects.filter(device=device, route=device.development_route))
    if created and gates and gates[0].stage in created:
        notifications.gate_open(gates[0])
    return gates


def next_open_gate(gates):
    """Gates open in stage order: only the first gate not yet approved can be approved."""
    return next((g for g in gates if g.status == "open"), None)


def approve_gate(gate, user, secret: str):
    """Approve the next open gate, with an electronic signature. Only someone holding the
    gate's approver role on the device may, only after the earlier stages are approved, and only
    while the stage's gate checks on the documentation route pass."""
    errors = []
    services._check_secret(errors, user, secret)
    if gate.approver_role not in device_roles(user, gate.device):
        errors.append(f"Requires role: {gate.approver_role} on {gate.device.name}.")
    if gate.status == "approved":
        errors.append("This gate is already approved.")
    else:
        upcoming = next_open_gate(ensure_gates(gate.device))
        if upcoming is not None and upcoming.pk != gate.pk:
            errors.append(f"Stage {upcoming.stage} ({upcoming.name}) must be approved first.")
    if gate.status != "approved":
        failing = doc_route.gate_check_failures(gate.device, gate.stage)
        if failing:
            errors.append("Gate checks not passing: " + "; ".join(failing)
                          + ". Fix them on the device page before signing.")
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        gate.status = "approved"
        gate.approved_by = user
        gate.approved_at = timezone.now()
        gate.save(_actor=user, _comment="Stage gate approved")
        services.sign(gate, user, secret, f"Approved stage gate: Stage {gate.stage}",
                      transition="approve_gate", from_status="open", to_status="approved")
        following = next_open_gate(ensure_gates(gate.device))
        if following is not None:
            notifications.gate_open(following)
    return gate


def gate_lanes(user, device, gates) -> list:
    """One lane per gate: its status, and whether this person can approve it now."""
    mine = device_roles(user, device)
    upcoming = next_open_gate(gates)
    return [{"gate": g, "can_approve": g is upcoming and g.approver_role in mine,
             "is_approver": g.approver_role in mine} for g in gates]


def _roles_text(roles) -> str:
    return " or ".join(r for r in wf.ROLES if r in roles)


def board(user, device) -> dict:
    """Columns of tasks for ``user`` on ``device``. Empty for people with no role there."""
    columns = {"todo": [], "waiting": [], "done": []}
    mine = device_roles(user, device)
    if not mine:
        return columns

    # Records: transitions restricted to specific roles (the same rule that drives the
    # "is now ..." notifications), so a record appears once per role-gated next step.
    records = Record.objects.filter(device=device).exclude(
        status__in=wf.TERMINAL_STATES).select_related("owner")
    for record in records:
        url = reverse("qms:record_detail", args=[record.ref])
        seen_todo = seen_waiting = False
        for t in wf.all_transitions(record.record_type):
            if record.status not in t.sources or set(t.roles) == set(wf.ANY_ROLE):
                continue
            if set(t.roles) & mine:
                if not seen_todo:
                    columns["todo"].append(Task(
                        record.type_label, f"{record.ref}: {record.title}",
                        f"Next step: {t.label}", url))
                    seen_todo = True
            elif record.owner_id == user.pk and not seen_waiting:
                columns["waiting"].append(Task(
                    record.type_label, f"{record.ref}: {record.title}",
                    f"Waiting for {_roles_text(t.roles)}: {t.label}", url))
                seen_waiting = True

    # Approver gates on this device's route that this person's role can approve now.
    upcoming = next_open_gate(ensure_gates(device))
    if upcoming is not None and upcoming.approver_role in mine:
        columns["todo"].append(Task(
            "Approver gate", f"Stage {upcoming.stage}: {upcoming.name}",
            f"Approve ({upcoming.approver_role})",
            reverse("qms:device_tasks", args=[device.code])))

    # Document versions on this device, and QMS-wide documents.
    versions = DocumentVersion.objects.filter(
        Q(document__device=device) | Q(document__device__isnull=True),
        status__in=["draft", "in_review", "approved"],
    ).select_related("document", "author")
    for v in versions:
        url = reverse("qms:document_detail", args=[v.document.number])
        title = f"{v.document.number} v{v.version}: {v.document.title}"
        is_author = v.author_id == user.pk
        if v.status == "draft" and is_author:
            columns["todo"].append(Task("Document", title, "Finish and submit for review", url))
        elif v.status == "in_review":
            if wf.QA in mine and not is_author:
                columns["todo"].append(Task("Document", title, "Approve (QA)", url))
            elif is_author:
                columns["waiting"].append(Task("Document", title, "Waiting for QA approval", url))
        elif v.status == "approved":
            if wf.QA in mine:
                columns["todo"].append(Task("Document", title, "Make effective (QA)", url))
            elif is_author:
                columns["waiting"].append(Task("Document", title,
                                               "Waiting for QA to make it effective", url))

    # Technical file builds waiting for the QA signature.
    if wf.QA in mine:
        for build in TechnicalFileBuild.objects.filter(device=device, approved_at__isnull=True):
            columns["todo"].append(Task(
                "Technical file", f"{build.label}",
                "Approve the technical file build (QA signature)",
                reverse("qms:device_detail", args=[device.code])))

    # Training assigned to this person for effective documents on this device.
    assignments = TrainingAssignment.objects.filter(
        user=user, completed_at__isnull=True, version__status="effective").filter(
        Q(version__document__device=device) | Q(version__document__device__isnull=True)
    ).select_related("version__document")
    for a in assignments:
        columns["todo"].append(Task(
            "Training", f"{a.version.document.number} v{a.version.version}: "
                        f"{a.version.document.title}",
            "Read the document and complete training", reverse("qms:my_training")))

    # Recent signatures this person made on this device.
    since = timezone.now() - timedelta(days=RECENT_DAYS)
    signed = Signature.objects.filter(
        signer=user, signed_at__gte=since, record__device=device
    ).select_related("record").order_by("-signed_at")[:10]
    for s in signed:
        columns["done"].append(Task(
            s.record.type_label, f"{s.record.ref}: {s.record.title}",
            f"Signed '{s.meaning}' on {s.signed_at:%d %b %Y}",
            reverse("qms:record_detail", args=[s.record.ref])))

    return columns
