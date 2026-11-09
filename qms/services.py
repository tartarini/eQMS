"""
Business operations. Every status change in the QMS goes through a function here, which checks
roles and preconditions, applies electronic signatures and writes the audit trail.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import notifications
from . import workflow as wf
from .models import (AuditEvent, Document, DocumentVersion, Hazard, PMSSchedule, Record,
                     Signature, Supplier, TrainingAssignment, TrainingRequirement, add_months,
                     verify_signing_credential)


class TransitionError(Exception):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [errors]
        super().__init__("; ".join(self.errors))


# --- shared helpers -------------------------------------------------------------

def user_has_role(user, roles, device=None) -> bool:
    """Role on ``device``; ``None`` for QMS-wide items (role held anywhere). See qms.roles."""
    from .roles import has_role
    return has_role(user, roles, device)


def require(errors: list, condition: bool, message: str):
    if not condition:
        errors.append(message)


def _device_error(user, device):
    """Team check: the person must be on the device's team (or have All-device access)."""
    from .access import can_access
    return [] if can_access(user, device) else ["You are not on this device's team."]


def _role_error(user, roles, device=None):
    if user_has_role(user, roles, device):
        return []
    where = f" on {device.name}" if device is not None else ""
    return ["Requires role: " + " or ".join(roles) + where + "."]


def sign(obj, user, secret: str, meaning: str, *, from_status="", to_status="",
         transition="", comment="") -> Signature:
    """Create an electronic signature over ``obj``'s current state. Caller checks the secret."""
    is_record = isinstance(obj, Record)
    signature = Signature.objects.create(
        record=obj if is_record else None,
        object_type="" if is_record else obj.audit_type,
        object_ref="" if is_record else obj.audit_ref,
        signer=user, signer_name=user.get_full_name() or user.get_username(),
        meaning=meaning, transition=transition, from_status=from_status, to_status=to_status,
        comment=comment, record_state_hash=obj.state_hash(),
    )
    AuditEvent.log("sign", obj=obj, actor=user, comment=comment,
                   changes={"meaning": meaning, "state_hash": signature.record_state_hash})
    return signature


def _check_secret(errors, user, secret):
    from .sso import signer_identity_errors
    identity = signer_identity_errors(user)
    if identity:
        errors.extend(identity)
        return
    if not verify_signing_credential(user, secret):
        errors.append("Signature failed: password or signing PIN not recognised.")


def _independent(errors, user, author):
    if (settings.QMS_REQUIRE_INDEPENDENT_APPROVAL and author is not None
            and author.pk == user.pk and not user.is_superuser):
        errors.append("Needs independent sign-off: the author cannot approve their own work.")


# --- quality record workflows -----------------------------------------------------

@dataclass
class TransitionOption:
    transition: wf.Transition
    allowed: bool
    blockers: list


def check_transition(record: Record, transition: wf.Transition, user, comment: str = "") -> list:
    """Return a list of reasons the transition cannot happen now (empty = allowed)."""
    errors = []
    if record.status not in transition.sources:
        return [f"Not available from status '{record.get_status_display()}'."]
    errors += _device_error(user, record.device)
    errors += _role_error(user, transition.roles, record.device)
    for name in transition.required:
        value = getattr(record, name)
        if value in (None, "", False) or (name == "risk_file_updated" and value == "pending"):
            label = Record._meta.get_field(name).verbose_name
            errors.append(f"'{label[:1].upper() + label[1:]}' must be filled in.")
    for check in transition.checks:
        msg = check(record)
        if msg:
            errors.append(msg)
    if transition.comment_required and not comment.strip():
        errors.append("A comment (rationale) is required.")
    if transition.independent:
        _independent(errors, user, record.created_by)
    return errors


def available_transitions(record: Record, user):
    options = []
    for t in wf.all_transitions(record.record_type):
        if record.status in t.sources:
            blockers = check_transition(record, t, user, comment="x")
            options.append(TransitionOption(t, not blockers, blockers))
    return options


def perform_transition(record: Record, name: str, user, comment: str = "",
                       password: str = "") -> Record:
    transition = wf.get_transition(record.record_type, name)
    with transaction.atomic():
        record = Record.objects.select_for_update().get(pk=record.pk)
        errors = check_transition(record, transition, user, comment)
        if transition.signature:
            _check_secret(errors, user, password)
        if errors:
            raise TransitionError(errors)

        from_status = record.status
        if transition.signature:
            sign(record, user, password, transition.signature, from_status=from_status,
                 to_status=transition.target, transition=transition.name, comment=comment)
        record.status = transition.target
        if transition.target in wf.TERMINAL_STATES:
            record.closed_at = timezone.now()
        record.save(_via_workflow=True)
        AuditEvent.log("transition", record=record, actor=user, comment=comment,
                       changes={"status": [from_status, transition.target],
                                "transition": transition.name})
        notifications.record_transitioned(record, user)
    return record


def generate_pms_activities(today: date = None, horizon_days: int = None) -> list:
    """Create PMS Activity records for schedules due within the horizon. Idempotent."""
    today = today or date.today()
    horizon = today + timedelta(days=horizon_days if horizon_days is not None
                                else settings.QMS_PMS_HORIZON_DAYS)
    created = []
    for schedule in PMSSchedule.objects.filter(active=True, next_due__lte=horizon):
        with transaction.atomic():
            schedule = PMSSchedule.objects.select_for_update().get(pk=schedule.pk)
            while schedule.next_due <= horizon:
                due = schedule.next_due
                period_start = add_months(due, -schedule.cadence_months) + timedelta(days=1)
                if not Record.objects.filter(pms_schedule=schedule, due_date=due).exists():
                    created.append(Record.objects.create(
                        record_type=wf.PMS_ACTIVITY, device=schedule.device,
                        title=f"{schedule.name} – due {due:%d %b %Y}",
                        description=schedule.description,
                        due_date=due, period_start=period_start, period_end=due,
                        pms_schedule=schedule,
                    ))
                schedule.next_due = add_months(due, schedule.cadence_months)
            schedule.save()
    return created


DEFAULT_PMS_SCHEDULES = [
    ("MHRA and FDA safety notices review", 1,
     "Check safety notices for similar devices; raise a Problem Report or CAPA if relevant."),
    ("SOUP and dependency vulnerability review", 1,
     "Review the SOUP list and known vulnerabilities; raise Change Requests for fixes."),
    ("Complaint and Problem Report trend review", 3,
     "Trend complaints and problems by severity, software item and site; raise a CAPA if a "
     "threshold is crossed."),
    ("Real-world performance monitoring", 3,
     "Compare real-world performance with the validated baseline; for AI devices, flag drift."),
    ("Subgroup performance review", 3,
     "Check performance across relevant subgroups (for example age, sex, ethnicity or site); "
     "raise a Problem Report for any gap."),
    ("Clinical site and user feedback round", 6,
     "Collect and summarise feedback; log Complaints."),
    ("Literature and similar-device review", 6, "Update the literature log and the risk file."),
    ("PMS report or PSUR", 12,
     "Prepare and sign the annual PMS report or PSUR for the technical file."),
    ("PMS plan review", 12, "Review and revise the PMS plan."),
]


def setup_device_pms(device, today: date = None) -> list:
    """Give a device the standard PMS schedule. Skips activities it already has."""
    import calendar
    today = today or date.today()
    created = []
    for name, months, desc in DEFAULT_PMS_SCHEDULES:
        first = add_months(today, months - 1)
        first = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
        obj, new = PMSSchedule.objects.get_or_create(
            device=device, name=name,
            defaults={"cadence_months": months, "next_due": first, "description": desc})
        if new:
            created.append(obj)
    return created


# --- document control ---------------------------------------------------------------

def _set_version_status(version, status, actor, comment="", **fields):
    from_status = version.status
    version.status = status
    for k, v in fields.items():
        setattr(version, k, v)
    version.save(_via_workflow=True, _actor=actor, _comment=comment)
    return from_status


def create_version(document: Document, user, *, version: str, change_summary: str, file=None,
                   change_request=None) -> DocumentVersion:
    errors = _device_error(user, document.device)
    require(errors, not document.obsolete, f"{document.number} is obsolete.")
    require(errors, document.open_version is None,
            f"{document.number} already has a revision in progress "
            f"({document.open_version}).")
    require(errors, bool(version.strip()), "Version is required.")
    if errors:
        raise TransitionError(errors)
    v = DocumentVersion(document=document, version=version.strip(), change_summary=change_summary,
                        file=file, change_request=change_request, author=user)
    v.save(_actor=user)
    return v


def submit_version(version: DocumentVersion, user) -> DocumentVersion:
    errors = _device_error(user, version.document.device)
    require(errors, version.status == "draft", "Only drafts can be submitted.")
    require(errors, bool(version.file), "Upload the document file before submitting.")
    require(errors, bool(version.change_summary.strip()), "A change summary is required.")
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        _set_version_status(version, "in_review", user, submitted_at=timezone.now())
        notifications.document_submitted(version)
    return version


def return_version(version: DocumentVersion, user, comment: str) -> DocumentVersion:
    errors = _device_error(user, version.document.device) + _role_error(
        user, [wf.QA], version.document.device)
    require(errors, version.status in ("in_review", "approved"),
            "Only versions in review or approved can be returned.")
    require(errors, bool(comment.strip()), "Say what needs to change.")
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        _set_version_status(version, "draft", user, f"Returned for changes: {comment}",
                            submitted_at=None, approved_at=None)
    return version


def approve_version(version: DocumentVersion, user, secret: str, comment="") -> DocumentVersion:
    errors = _device_error(user, version.document.device) + _role_error(
        user, [wf.QA], version.document.device)
    require(errors, version.status == "in_review", "Only versions in review can be approved.")
    _independent(errors, user, version.author)
    require(errors, version.verify(), "File integrity check failed: the file changed after "
                                      "upload. Return the version for a fresh upload.")
    _check_secret(errors, user, secret)
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        sign(version, user, secret, "Document approval", from_status="in_review",
             to_status="approved", transition="approve", comment=comment)
        _set_version_status(version, "approved", user, comment, approved_at=timezone.now())
    return version


def make_effective(version: DocumentVersion, user, effective: date = None) -> DocumentVersion:
    errors = _device_error(user, version.document.device) + _role_error(
        user, [wf.QA], version.document.device)
    require(errors, version.status == "approved", "Only approved versions can become effective.")
    if errors:
        raise TransitionError(errors)
    effective = effective or date.today()
    with transaction.atomic():
        for old in version.document.versions.filter(status="effective"):
            _set_version_status(old, "superseded", user, f"Superseded by v{version.version}")
        _set_version_status(version, "effective", user, effective_date=effective,
                            next_review_date=version.compute_review_date(effective))
        assign_training_for_version(version)
        notifications.document_effective(version)
    return version


def review_no_change(version: DocumentVersion, user, secret: str, comment: str):
    """Periodic review concluding the document is still correct; resets the review date."""
    errors = _device_error(user, version.document.device) + _role_error(
        user, [wf.QA], version.document.device)
    require(errors, version.status == "effective", "Only the effective version can be reviewed.")
    require(errors, bool(comment.strip()), "Record what was reviewed.")
    _check_secret(errors, user, secret)
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        sign(version, user, secret, "Periodic review: no change needed", comment=comment)
        version.next_review_date = version.compute_review_date(date.today())
        version.save(_via_workflow=True, _actor=user, _comment=f"Periodic review: {comment}")
    return version


def obsolete_document(document: Document, user, secret: str, comment: str):
    errors = _device_error(user, document.device) + _role_error(user, [wf.QA], document.device)
    require(errors, not document.obsolete, "Already obsolete.")
    require(errors, bool(comment.strip()), "Give the reason for withdrawal.")
    _check_secret(errors, user, secret)
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        sign(document, user, secret, "Document withdrawal", comment=comment)
        for v in document.versions.filter(status__in=["effective", "draft", "in_review",
                                                      "approved"]):
            _set_version_status(v, "obsolete", user, comment)
        document.obsolete = True
        document.save(_via_workflow=True, _actor=user, _comment=comment)
    return document


# --- training -------------------------------------------------------------------------

def _required_users(document):
    """People holding a required role: on the document's device, or anywhere for a QMS-wide
    document."""
    from .roles import users_with_roles
    roles = list(TrainingRequirement.objects.filter(document=document, active=True)
                 .values_list("group__name", flat=True))
    return users_with_roles(roles, document.device) if roles else []


def assign_training_for_version(version: DocumentVersion) -> list:
    if version.status != "effective":
        return []
    due = date.today() + timedelta(days=settings.QMS_TRAINING_DUE_DAYS)
    created = []
    for user in _required_users(version.document):
        assignment, new = TrainingAssignment.objects.get_or_create(
            user=user, version=version, defaults={"due_date": due})
        if new:
            created.append(assignment)
            notifications.training_assigned(assignment)
    return created


def sync_training() -> list:
    """Assign any missing training, e.g. for people who joined a role after a document went live."""
    created = []
    for version in DocumentVersion.objects.filter(status="effective",
                                                  document__obsolete=False):
        created += assign_training_for_version(version)
    return created


def complete_training(assignment: TrainingAssignment, user, secret: str):
    errors = []
    require(errors, assignment.user_id == user.pk, "You can only sign off your own training.")
    require(errors, assignment.completed_at is None, "Already completed.")
    require(errors, assignment.version.status == "effective",
            "This version is no longer effective; complete the current version instead.")
    _check_secret(errors, user, secret)
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        sign(assignment.version, user, secret, "Read and understood")
        assignment.completed_at = timezone.now()
        assignment.save(_via_workflow=True, _actor=user)
    return assignment


def training_matrix(viewer=None):
    """Rows: users in any QMS role. Columns: documents with training requirements."""
    from .access import can_access
    docs = [d for d in Document.objects.filter(obsolete=False, training_requirements__active=True)
            .distinct() if viewer is None or can_access(viewer, d.device)]
    from .roles import device_roles, users_with_roles
    users = users_with_roles(wf.ANY_ROLE)
    required = {}
    for r in TrainingRequirement.objects.filter(active=True).select_related("group"):
        required.setdefault(r.document_id, set()).add(r.group.name)
    effective = {d.pk: d.effective_version for d in docs}
    assignments = {(a.user_id, a.version_id): a for a in TrainingAssignment.objects.filter(
        version__in=[v for v in effective.values() if v])}
    rows = []
    for u in users:
        cells = []
        for d in docs:
            if d.device_id and not can_access(u, d.device):
                cells.append(("n/a", None))
            elif not (device_roles(u, d.device) & required.get(d.pk, set())):
                cells.append(("n/a", None))
            elif not effective[d.pk]:
                cells.append(("no effective version", None))
            else:
                a = assignments.get((u.pk, effective[d.pk].pk))
                cells.append((a.status if a else "not assigned", a))
        rows.append((u, cells))
    return docs, rows


# --- risk management -----------------------------------------------------------------

def hazard_acceptance_blockers(hazard: Hazard) -> list:
    errors = []
    require(errors, hazard.status == "open", "Only open hazards can be accepted.")
    require(errors, bool(hazard.severity_residual and hazard.probability_residual),
            "Score the residual severity and probability.")
    controls = list(hazard.controls.all())
    if hazard.initial_level != "acceptable":
        require(errors, bool(controls), "A risk that is not acceptable needs risk controls.")
    unverified = [c for c in controls if not c.verified]
    require(errors, not unverified,
            f"{len(unverified)} risk control(s) not verified." if unverified else "")
    if hazard.residual_level and hazard.residual_level != "acceptable":
        require(errors, bool(hazard.benefit_risk_rationale.strip()),
                "Residual risk is not acceptable by the matrix: a benefit-risk rationale "
                "is required.")
    return errors


def accept_hazard(hazard: Hazard, user, secret: str, comment: str = ""):
    errors = (_device_error(user, hazard.device) + _role_error(user, [wf.QA], hazard.device)
              + hazard_acceptance_blockers(hazard))
    _check_secret(errors, user, secret)
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        sign(hazard, user, secret, "Risk acceptance", from_status="open", to_status="accepted",
             comment=comment)
        _set_hazard_status(hazard, "accepted", user, comment)
    return hazard


def reopen_hazard(hazard: Hazard, user, comment: str):
    errors = _device_error(user, hazard.device) + _role_error(user, [wf.QA], hazard.device)
    require(errors, hazard.status != "open", "Already open.")
    require(errors, bool(comment.strip()), "Give the reason for reopening.")
    if errors:
        raise TransitionError(errors)
    _set_hazard_status(hazard, "open", user, comment)
    return hazard


def retire_hazard(hazard: Hazard, user, secret: str, comment: str):
    errors = _device_error(user, hazard.device) + _role_error(user, [wf.QA], hazard.device)
    require(errors, hazard.status != "retired", "Already retired.")
    require(errors, bool(comment.strip()), "Explain why the hazard no longer applies.")
    _check_secret(errors, user, secret)
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        sign(hazard, user, secret, "Hazard retirement", from_status=hazard.status,
             to_status="retired", comment=comment)
        _set_hazard_status(hazard, "retired", user, comment)
    return hazard


def _set_hazard_status(hazard, status, user, comment):
    hazard.status = status
    hazard.save(_via_workflow=True, _actor=user, _comment=comment)


def risk_matrix(which="initial", device=None, hazards=None):
    """5x5 counts of open and accepted hazards, rows = severity 5..1, cols = probability 1..5."""
    from .models import risk_level
    grid = {(s, p): [] for s in range(1, 6) for p in range(1, 6)}
    if hazards is None:
        hazards = Hazard.objects.all()
        if device is not None:
            hazards = hazards.filter(device=device)
    for h in hazards.exclude(status="retired"):
        s, p = ((h.severity_initial, h.probability_initial) if which == "initial"
                else (h.severity_residual, h.probability_residual))
        if s and p:
            grid[(s, p)].append(h)
    return [(s, [(p, grid[(s, p)], risk_level(s, p)) for p in range(1, 6)])
            for s in range(5, 0, -1)]


# --- suppliers -------------------------------------------------------------------------

def evaluate_supplier(supplier: Supplier, user, secret: str, outcome: str, notes: str):
    errors = _role_error(user, [wf.QA])
    require(errors, outcome in dict(Supplier.STATUSES) and outcome != "proposed",
            "Choose an evaluation outcome.")
    require(errors, bool(notes.strip()), "Record the evaluation evidence and conclusion.")
    _check_secret(errors, user, secret)
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        old = supplier.status
        supplier.status = outcome
        supplier.last_evaluated = date.today()
        sign(supplier, user, secret, "Supplier evaluation", from_status=old, to_status=outcome,
             comment=notes)
        supplier.save(_via_workflow=True, _actor=user, _comment=notes)
    return supplier
