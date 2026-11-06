from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import services
from django.http import Http404

from .access import (can_access, current_device, form_page, qms_member, require_access, run,
                     scope)
from .forms import (HazardForm, RiskControlForm, SignForm, SoupItemForm,
                    SupplierEvaluationForm, SupplierForm)
from .models import (LEVEL_LABELS, AuditEvent, Hazard, RiskControl, Signature, SoupItem,
                     Supplier)


# --- risk management --------------------------------------------------------------------

@qms_member
def hazard_list(request):
    status = request.GET.get("status", "active")
    hazards = scope(Hazard.objects.select_related("device").prefetch_related("controls"), request)
    if status == "active":
        hazards = hazards.exclude(status="retired")
    return render(request, "qms/hazard_list.html", {
        "hazards": hazards, "status": status, "levels": LEVEL_LABELS,
        "matrix_initial": services.risk_matrix("initial", hazards=hazards),
        "matrix_residual": services.risk_matrix("residual", hazards=hazards),
    })


@qms_member
def hazard_create(request):
    form = HazardForm(request.POST or None, user=request.user,
                      initial={"device": current_device(request)})
    if request.method == "POST" and form.is_valid():
        h = form.save()
        messages.success(request, f"{h.ref} added to the risk register.")
        return redirect("qms:hazard_detail", ref=h.ref)
    return form_page(request, form, "New hazard", reverse("qms:hazard_list"),
                     intro="Severity and probability use 1–5 scales. Score the residual risk "
                           "once risk controls are defined.")


@qms_member
def hazard_edit(request, ref):
    h = get_object_or_404(Hazard, ref=ref)
    require_access(request, h.device)
    if h.is_locked:
        messages.error(request, f"{h.ref} is {h.status}; reopen it to make changes.")
        return redirect("qms:hazard_detail", ref=ref)
    form = HazardForm(request.POST or None, instance=h, user=request.user)
    if request.method == "POST" and form.is_valid():
        if run(request, form.save, success="Saved."):
            return redirect("qms:hazard_detail", ref=ref)
    return form_page(request, form, f"Edit {h.ref}", reverse("qms:hazard_detail", args=[ref]))


@qms_member
def hazard_detail(request, ref):
    h = get_object_or_404(Hazard.objects.select_related("owner"), ref=ref)
    require_access(request, h.device)
    controls = list(h.controls.select_related("implemented_by"))
    refs = [h.audit_ref] + [c.audit_ref for c in controls]
    return render(request, "qms/hazard_detail.html", {
        "h": h, "controls": controls, "levels": LEVEL_LABELS,
        "records": h.records.all(), "control_form": RiskControlForm(), "sign_form": SignForm(),
        "blockers": services.hazard_acceptance_blockers(h) if h.status == "open" else [],
        "signatures": Signature.for_object(h),
        "events": AuditEvent.objects.filter(object_ref__in=refs).order_by("-id"),
    })


@qms_member
def control_add(request, ref):
    h = get_object_or_404(Hazard, ref=ref)
    require_access(request, h.device)
    form = RiskControlForm(request.POST or None, hazard=h, user=request.user)
    if request.method == "POST" and form.is_valid():
        control = form.save(commit=False)
        control.hazard = h
        if run(request, control.save, success="Risk control added."):
            return redirect("qms:hazard_detail", ref=ref)
    return form_page(request, form, f"Add risk control to {h.ref}",
                     reverse("qms:hazard_detail", args=[ref]))


@qms_member
def control_edit(request, pk):
    c = get_object_or_404(RiskControl, pk=pk)
    require_access(request, c.hazard.device)
    form = RiskControlForm(request.POST or None, instance=c, hazard=c.hazard, user=request.user)
    if request.method == "POST" and form.is_valid():
        if run(request, form.save, success="Risk control updated."):
            return redirect("qms:hazard_detail", ref=c.hazard.ref)
    return form_page(request, form, f"Edit control on {c.hazard.ref}",
                     reverse("qms:hazard_detail", args=[c.hazard.ref]))


@qms_member
@require_POST
def hazard_action(request, ref, action):
    h = get_object_or_404(Hazard, ref=ref)
    require_access(request, h.device)
    form = SignForm(request.POST)
    form.is_valid()
    comment, secret = form.cleaned_data.get("comment", ""), form.cleaned_data.get("password", "")
    if action == "accept":
        run(request, services.accept_hazard, h, request.user, secret, comment,
            success=f"{h.ref} residual risk accepted.")
    elif action == "reopen":
        run(request, services.reopen_hazard, h, request.user, comment,
            success=f"{h.ref} reopened.")
    elif action == "retire":
        run(request, services.retire_hazard, h, request.user, secret, comment,
            success=f"{h.ref} retired.")
    return redirect("qms:hazard_detail", ref=ref)


# --- suppliers and SOUP ----------------------------------------------------------------

@qms_member
def supplier_list(request):
    return render(request, "qms/supplier_list.html", {
        "suppliers": Supplier.objects.all(),
        "soup": scope(SoupItem.objects.select_related("supplier").prefetch_related("devices"),
                      request, "devices", allow_shared=True),
    })


@qms_member
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        s = form.save()
        messages.success(request, f"{s} added. It needs a signed evaluation before approval.")
        return redirect("qms:supplier_detail", pk=s.pk)
    return form_page(request, form, "New supplier", reverse("qms:supplier_list"))


@qms_member
def supplier_edit(request, pk):
    s = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=s)
    if request.method == "POST" and form.is_valid():
        if run(request, form.save, success="Saved."):
            return redirect("qms:supplier_detail", pk=pk)
    return form_page(request, form, f"Edit {s}", reverse("qms:supplier_detail", args=[pk]))


@qms_member
def supplier_detail(request, pk):
    s = get_object_or_404(Supplier, pk=pk)
    return render(request, "qms/supplier_detail.html", {
        "s": s, "soup": s.soup_items.all(), "eval_form": SupplierEvaluationForm(),
        "signatures": Signature.for_object(s),
        "events": AuditEvent.for_object(s).order_by("-id"),
    })


@qms_member
@require_POST
def supplier_evaluate(request, pk):
    s = get_object_or_404(Supplier, pk=pk)
    form = SupplierEvaluationForm(request.POST)
    if form.is_valid():
        run(request, services.evaluate_supplier, s, request.user,
            form.cleaned_data["password"], form.cleaned_data["outcome"],
            form.cleaned_data["notes"], success="Evaluation signed and recorded.")
    else:
        messages.error(request, "Choose an outcome, record notes and sign.")
    return redirect("qms:supplier_detail", pk=pk)


@qms_member
def soup_create(request):
    device = current_device(request)
    form = SoupItemForm(request.POST or None, user=request.user,
                        initial={"supplier": request.GET.get("supplier"),
                                 "devices": [device] if device else []})
    if request.method == "POST" and form.is_valid():
        item = form.save()
        messages.success(request, f"{item} added to the SOUP list.")
        return redirect("qms:supplier_list")
    return form_page(request, form, "New SOUP item", reverse("qms:supplier_list"))


@qms_member
def soup_edit(request, pk):
    item = get_object_or_404(SoupItem, pk=pk)
    linked = list(item.devices.all())
    if linked and not any(can_access(request.user, d) for d in linked):
        raise Http404("Not found")
    form = SoupItemForm(request.POST or None, instance=item, user=request.user)
    if request.method == "POST" and form.is_valid():
        if run(request, form.save, success="Saved."):
            return redirect("qms:supplier_list")
    return form_page(request, form, f"Edit {item}", reverse("qms:supplier_list"),
                     intro="When you review published anomalies and vulnerabilities, update "
                           "'Known anomalies' and set 'Last anomaly review' to today.")
