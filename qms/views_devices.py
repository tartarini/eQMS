from collections import Counter

from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import services, techfile
from . import workflow as wf
from .access import (SESSION_DEVICE_KEY, accessible_devices, form_page, qms_member,
                     require_access, run, sees_all_devices)
from .forms import DeviceForm, SignForm, TeamMemberForm
from .models import AuditEvent, Device, DeviceMembership, Signature, TechnicalFileBuild


@qms_member
@require_POST
def set_device(request):
    """Header switcher: choose a device to focus on, or all devices."""
    device_id = request.POST.get("device")
    if device_id and accessible_devices(request.user).filter(pk=device_id, active=True).exists():
        request.session[SESSION_DEVICE_KEY] = int(device_id)
    else:
        request.session.pop(SESSION_DEVICE_KEY, None)
    nxt = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(nxt, {request.get_host()}):
        nxt = reverse("qms:dashboard")
    return redirect(nxt)


@qms_member
def device_list(request):
    devices = accessible_devices(request.user)
    rows = []
    for d in devices:
        labels = dict(wf.RECORD_TYPES)
        open_counts = Counter(labels[t] for t in d.records.exclude(
            status__in=wf.TERMINAL_STATES).values_list("record_type", flat=True))
        rows.append((d, sorted(open_counts.items()),
                     d.technical_files.filter(status="approved").first()))
    return render(request, "qms/device_list.html", {"rows": rows})


@qms_member
def device_create(request):
    if not services.user_has_role(request.user, [wf.QA]):
        messages.error(request, "Requires role: QA.")
        return redirect("qms:device_list")
    form = DeviceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        device = form.save(commit=False)
        device.save(_actor=request.user)
        DeviceMembership(device=device, user=request.user, note="Created the device") \
            .save(_actor=request.user)
        schedules = services.setup_device_pms(device)
        request.session[SESSION_DEVICE_KEY] = device.pk
        messages.success(request, f"{device.name} added with {len(schedules)} PMS activities "
                                  "scheduled. It is now your selected device.")
        return redirect("qms:device_detail", code=device.code)
    return form_page(request, form, "New medical device", reverse("qms:device_list"),
                     intro="Record the device's regulatory particulars. They form section 1 of "
                           "its technical file; you can complete them later.")


@qms_member
def device_edit(request, code):
    device = get_object_or_404(Device, code=code)
    require_access(request, device)
    if not services.user_has_role(request.user, [wf.QA]):
        messages.error(request, "Requires role: QA.")
        return redirect("qms:device_detail", code=code)
    form = DeviceForm(request.POST or None, instance=device)
    if request.method == "POST" and form.is_valid():
        d = form.save(commit=False)
        d.save(_actor=request.user)
        messages.success(request, "Saved.")
        return redirect("qms:device_detail", code=d.code)
    return form_page(request, form, f"Edit {device.name}",
                     reverse("qms:device_detail", args=[code]))


@qms_member
def device_detail(request, code):
    device = get_object_or_404(Device, code=code)
    require_access(request, device)
    data = techfile.gather(device)
    checks = techfile.completeness_checks(device, data)
    records = device.records.all()
    counts = [(label, records.filter(record_type=t).exclude(status__in=wf.TERMINAL_STATES).count(),
               records.filter(record_type=t).count(), t) for t, label in wf.RECORD_TYPES]
    sections = [(code_, label, data["sections"].get(code_, []))
                for code_, label in techfile.TECH_FILE_SECTIONS if code_]
    builds = device.technical_files.select_related("generated_by")
    return render(request, "qms/device_detail.html", {
        "device": device, "data": data, "counts": counts, "sections": sections,
        "errors": [c for c in checks if c["level"] == "error"],
        "warnings": [c for c in checks if c["level"] == "warning"],
        "builds": builds, "sign_form": SignForm(),
        "is_qa": services.user_has_role(request.user, [wf.QA]),
        "signatures": Signature.objects.filter(object_type="Technical File Build",
                                               object_ref__in=[b.label for b in builds]),
        "events": AuditEvent.objects.filter(
            Q(object_ref__in=[device.code] + [b.label for b in builds])
            | Q(object_type="Device Membership", object_ref__endswith=f"@ {device.code}"))
            .order_by("-id")[:50],
        "team": device.memberships.filter(active=True).select_related("user"),
        "team_form": TeamMemberForm(device=device),
        "can_manage_team": _can_manage_team(request.user, device),
    })


def _can_manage_team(user, device):
    """QA on the device's team, or anyone with All-device access, manages its team."""
    return sees_all_devices(user) or (
        services.user_has_role(user, [wf.QA])
        and device.memberships.filter(user=user, active=True).exists())


@qms_member
@require_POST
def team_add(request, code):
    device = get_object_or_404(Device, code=code)
    require_access(request, device)
    if not _can_manage_team(request.user, device):
        messages.error(request, "Only QA on this device's team can change it.")
        return redirect("qms:device_detail", code=code)
    form = TeamMemberForm(request.POST, device=device)
    if form.is_valid():
        user = form.cleaned_data["user"]
        m, created = DeviceMembership.objects.get_or_create(
            device=device, user=user, defaults={"note": form.cleaned_data["note"]})
        if not created:
            m.active = True
            m.note = form.cleaned_data["note"] or m.note
            m.save(_actor=request.user)
        services.sync_training()
        messages.success(request, f"{user.get_full_name() or user.username} added to the "
                                  f"{device.name} team.")
    else:
        messages.error(request, "Choose a person to add.")
    return redirect("qms:device_detail", code=code)


@qms_member
@require_POST
def team_remove(request, pk):
    m = get_object_or_404(DeviceMembership, pk=pk)
    require_access(request, m.device)
    if not _can_manage_team(request.user, m.device):
        messages.error(request, "Only QA on this device's team can change it.")
    elif m.device.memberships.filter(active=True).count() == 1:
        messages.error(request, "A device needs at least one team member.")
    else:
        m.active = False
        m.save(_actor=request.user, _comment="Removed from team")
        messages.success(request, f"{m.user.get_username()} removed from the team. Their "
                                  "past records and signatures are kept.")
    return redirect("qms:device_detail", code=m.device.code)


@qms_member
def techfile_preview(request, code):
    device = get_object_or_404(Device, code=code)
    require_access(request, device)
    return HttpResponse(techfile.preview_html(device, request.user))


@qms_member
@require_POST
def techfile_generate(request, code):
    device = get_object_or_404(Device, code=code)
    require_access(request, device)
    build = run(request, techfile.generate_technical_file, device, request.user)
    if build:
        msg = f"{build.label} generated"
        if build.error_count or build.warning_count:
            msg += f" with {build.error_count} error(s) and {build.warning_count} warning(s)"
        messages.success(request, msg + ".")
    return redirect("qms:device_detail", code=code)


@qms_member
def techfile_download(request, pk):
    build = get_object_or_404(TechnicalFileBuild, pk=pk)
    require_access(request, build.device)
    if not build.verify():
        messages.error(request, f"Integrity check failed for {build.label}: the stored package "
                                "does not match its recorded checksum.")
        return redirect("qms:device_detail", code=build.device.code)
    return FileResponse(build.package.open("rb"), as_attachment=True,
                        filename=f"{build.label}.zip")


@qms_member
@require_POST
def techfile_approve(request, pk):
    build = get_object_or_404(TechnicalFileBuild, pk=pk)
    require_access(request, build.device)
    form = SignForm(request.POST)
    form.is_valid()
    run(request, techfile.approve_technical_file, build, request.user,
        form.cleaned_data.get("password", ""), form.cleaned_data.get("comment", ""),
        success=f"{build.label} approved and signed.")
    return redirect("qms:device_detail", code=build.device.code)
