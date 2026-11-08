import csv
from collections import Counter
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import workflow as wf
from .access import (can_access, current_device, form_page, qms_member, require_access, run,
                     scope, sees_all_devices)
from .forms import AttachmentForm, LinkForm, SigningPinForm, TransitionForm, record_form_class
from .models import (Attachment, AuditEvent, Document, Hazard, ImmutableError, Record,
                     RecordLink, Signature, SigningPin, SoupItem, Supplier, TrainingAssignment,
                     verify_audit_chain)
from .services import available_transitions, perform_transition
from .signals import log_security


def dashboard(request):
    """The landing page for visitors; the dashboard for people who are signed in."""
    if not request.user.is_authenticated:
        from .views_access import landing
        return landing(request)
    return _dashboard(request)


@qms_member
def _dashboard(request):
    device = current_device(request)
    open_records = scope(Record.objects.exclude(status__in=wf.TERMINAL_STATES), request)
    counts = Counter(open_records.values_list("record_type", flat=True))
    by_type = [(code, label, counts.get(code, 0)) for code, label in wf.RECORD_TYPES]
    with_deadline = [r for r in open_records.filter(
        record_type__in=[wf.INCIDENT, wf.CAPA, wf.PMS_ACTIVITY]) if r.next_deadline]
    with_deadline.sort(key=lambda r: r.next_deadline)
    chain_ok, bad_id = verify_audit_chain()
    soon = timezone.localdate() + timedelta(days=60)
    docs = scope(Document.objects.filter(obsolete=False), request, allow_shared=True)
    docs_due = [d for d in docs if d.next_review_date and d.next_review_date <= soon]
    return render(request, "qms/dashboard.html", {
        "by_type": by_type, "deadlines": with_deadline[:15],
        "safety": open_records.filter(patient_safety_impact="yes")[:15],
        "mine": open_records.filter(owner=request.user)[:15],
        "chain_ok": chain_ok, "bad_id": bad_id,
        "my_training": TrainingAssignment.objects.filter(
            user=request.user, completed_at__isnull=True, version__status="effective")
            .select_related("version__document"),
        "docs_due": docs_due,
        "docs_in_review": docs.filter(versions__status="in_review").distinct(),
        "unacceptable": [h for h in scope(Hazard.objects.exclude(status="retired"), request)
                         if (h.residual_level or h.initial_level) == "unacceptable"],
        "suppliers_due": [s for s in Supplier.objects.exclude(status="disqualified")
                          if s.evaluation_overdue],
        "soup_due": sum(1 for s in scope(SoupItem.objects.filter(active=True), request, "devices",
                                         allow_shared=True)
                        if s.review_overdue),
        "device": device,
    })


# --- quality records ------------------------------------------------------------------

@qms_member
def record_list(request):
    records = scope(Record.objects.select_related("owner", "device"), request)
    record_type = request.GET.get("type", "")
    status = request.GET.get("status", "open")
    q = request.GET.get("q", "").strip()
    if record_type:
        records = records.filter(record_type=record_type)
    if status == "open":
        records = records.exclude(status__in=wf.TERMINAL_STATES)
    elif status == "closed":
        records = records.filter(status__in=wf.TERMINAL_STATES)
    if q:
        records = records.filter(Q(ref__icontains=q) | Q(title__icontains=q)
                                 | Q(description__icontains=q))
    return render(request, "qms/record_list.html", {
        "records": records[:500], "record_types": wf.RECORD_TYPES,
        "record_type": record_type, "status": status, "q": q,
    })


@qms_member
def record_create(request, record_type):
    if record_type not in dict(wf.RECORD_TYPES):
        raise Http404
    form = record_form_class(record_type)(request.POST or None, user=request.user,
                                          initial={"device": current_device(request)})
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.record_type = record_type
        record.created_by = request.user
        record.save()
        form.save_m2m()
        messages.success(request, f"{record.ref} created.")
        return redirect("qms:record_detail", ref=record.ref)
    return form_page(request, form, f"New {dict(wf.RECORD_TYPES)[record_type]}",
                     reverse("qms:dashboard"),
                     intro="Do not enter patient or participant data: no names, NHS or hospital "
                           "numbers, identifiable images or recordings. Use anonymised IDs.")


@qms_member
def record_edit(request, ref):
    record = get_object_or_404(Record, ref=ref)
    require_access(request, record.device)
    if record.is_locked:
        messages.error(request, f"{record.ref} is {record.get_status_display().lower()} "
                                "and locked against edits.")
        return redirect("qms:record_detail", ref=ref)
    form = record_form_class(record.record_type)(request.POST or None, instance=record,
                                                 user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect("qms:record_detail", ref=ref)
    return form_page(request, form, f"Edit {record.ref}",
                     reverse("qms:record_detail", args=[ref]))


@qms_member
def record_detail(request, ref):
    record = get_object_or_404(Record.objects.select_related("owner", "created_by"), ref=ref)
    require_access(request, record.device)
    fields = []
    for name in wf.TYPE_FIELDS[record.record_type]:
        f = Record._meta.get_field(name)
        if name == "hazards":
            value = record.hazards.all()
        else:
            display = getattr(record, f"get_{name}_display", None)
            value = display() if display and getattr(record, name) else getattr(record, name)
            if isinstance(value, bool):
                value = "Yes" if value else "No"
        fields.append((name, f.verbose_name[:1].upper() + f.verbose_name[1:], value))
    return render(request, "qms/record_detail.html", {
        "record": record, "fields": fields,
        "transitions": available_transitions(record, request.user),
        "transition_form": TransitionForm(),
        "link_form": LinkForm(source=record, user=request.user),
        "attachment_form": AttachmentForm(),
        "outgoing": record.outgoing_links.select_related("target"),
        "incoming": [link for link in record.incoming_links.select_related("source__device")
                     if can_access(request.user, link.source.device)],
        "signatures": record.signatures.all(),
        "events": record.audit_events.order_by("-id"),
        "states": [(s, s.replace("_", " ").capitalize())
                   for s in wf.WORKFLOWS[record.record_type]["states"]],
        "doc_versions": record.document_versions.select_related("document"),
        "risk_controls": record.risk_controls.select_related("hazard"),
    })


@qms_member
@require_POST
def record_transition(request, ref, name):
    record = get_object_or_404(Record, ref=ref)
    require_access(request, record.device)
    form = TransitionForm(request.POST)
    form.is_valid()
    try:
        wf.get_transition(record.record_type, name)
    except KeyError:
        raise Http404
    result = run(request, perform_transition, record, name, request.user,
                 comment=form.cleaned_data.get("comment", ""),
                 password=form.cleaned_data.get("password", ""))
    if result:
        messages.success(request, f"{result.ref} is now {result.get_status_display().lower()}.")
    return redirect("qms:record_detail", ref=ref)


@qms_member
@require_POST
def record_link(request, ref):
    record = get_object_or_404(Record, ref=ref)
    require_access(request, record.device)
    if record.is_locked:
        messages.error(request, f"{record.ref} is locked.")
        return redirect("qms:record_detail", ref=ref)
    form = LinkForm(request.POST, source=record, user=request.user)
    if form.is_valid():
        try:
            RecordLink.objects.create(source=record, target=form.cleaned_data["target"],
                                      link_type=form.cleaned_data["link_type"],
                                      created_by=request.user)
            messages.success(request, "Link added.")
        except IntegrityError:
            messages.error(request, "That link already exists.")
    else:
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
    return redirect("qms:record_detail", ref=ref)


@qms_member
@require_POST
def record_unlink(request, ref, link_id):
    link = get_object_or_404(RecordLink, pk=link_id, source__ref=ref)
    require_access(request, link.source.device)
    try:
        link.delete()
        messages.success(request, "Link removed.")
    except ImmutableError as exc:
        messages.error(request, str(exc))
    return redirect("qms:record_detail", ref=ref)


@qms_member
@require_POST
def record_attach(request, ref):
    record = get_object_or_404(Record, ref=ref)
    require_access(request, record.device)
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        att = form.save(commit=False)
        att.record = record
        att.uploaded_by = request.user
        att.original_name = request.FILES["file"].name
        if run(request, att.save, success=f"Attached {att.original_name}."):
            AuditEvent.log("attach", record=record, actor=request.user,
                           changes={"file": att.original_name, "sha256": att.sha256})
    else:
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
    return redirect("qms:record_detail", ref=ref)


@qms_member
def attachment_download(request, pk):
    att = get_object_or_404(Attachment, pk=pk)
    require_access(request, att.record.device)
    if not att.verify():
        messages.error(request, f"Integrity check failed for {att.original_name}: the stored "
                                "file does not match its recorded checksum.")
        return redirect("qms:record_detail", ref=att.record.ref)
    return FileResponse(att.file.open("rb"), as_attachment=True, filename=att.original_name)


# --- audit ----------------------------------------------------------------------------

@qms_member
def audit_log(request):
    if not sees_all_devices(request.user):
        messages.info(request, "The full audit trail needs All-device access. Each record, "
                               "document, hazard and device shows its own trail.")
        return redirect("qms:dashboard")
    events = AuditEvent.objects.select_related("record").order_by("-id")
    kind = request.GET.get("kind", "")
    if kind == "security":
        events = events.filter(action="security")
    elif kind == "signatures":
        events = events.filter(action="sign")
    q = request.GET.get("q", "").strip()
    if q:
        events = events.filter(Q(record__ref__icontains=q) | Q(object_ref__icontains=q)
                               | Q(actor_name__icontains=q))
    ok, bad_id = verify_audit_chain()
    return render(request, "qms/audit_log.html", {"events": events[:300], "kind": kind,
                                                  "q": q, "chain_ok": ok, "bad_id": bad_id})


@qms_member
def audit_export(request, ref=None):
    """CSV of the audit trail, for one record or the whole system."""
    events = AuditEvent.objects.select_related("record").order_by("id")
    filename = "qms_audit_trail.csv"
    if not ref and not sees_all_devices(request.user):
        raise Http404("Not found")
    if ref:
        record = get_object_or_404(Record, ref=ref)
        require_access(request, record.device)
        events = events.filter(record=record)
        filename = f"{ref}_audit_trail.csv"
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(["id", "timestamp", "subject", "actor", "action", "changes", "comment",
                     "prev_hash", "hash"])
    for e in events.iterator():
        writer.writerow([e.id, e.timestamp.isoformat(), e.subject, e.actor_name, e.action,
                         e.changes, e.comment, e.prev_hash, e.hash])
    return response


# --- account --------------------------------------------------------------------------

@login_required
def signing_pin(request):
    user = request.user
    if not user.has_usable_password():
        login_at = request.session.get("qms_login_at")
        fresh = login_at and timezone.now() - datetime.fromisoformat(login_at) < timedelta(
            minutes=settings.QMS_PIN_REAUTH_MINUTES)
        if not fresh:
            messages.info(request, "For security, sign out and sign in again, then set your "
                                   f"PIN within {settings.QMS_PIN_REAUTH_MINUTES} minutes.")
            return redirect("qms:dashboard")
    form = SigningPinForm(request.POST or None, user=user)
    if request.method == "POST" and form.is_valid():
        pin, _ = SigningPin.objects.get_or_create(user=user, defaults={"pin_hash": ""})
        pin.set_pin(form.cleaned_data["pin"])
        pin.save()
        log_security(user, "signing PIN set", actor=user)
        messages.success(request, "Signing PIN saved. Use it when signing records.")
        return redirect("qms:dashboard")
    has_pin = SigningPin.objects.filter(user=user).exists()
    return form_page(request, form, "Signing PIN", reverse("qms:dashboard"), intro=(
        "Your signing PIN replaces your password when you sign approvals. "
        + ("You signed in with single sign-on, so you need a PIN before you can sign. "
           if not user.has_usable_password() else "")
        + ("A PIN is already set; saving replaces it." if has_pin else "")))
