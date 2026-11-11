from collections import Counter

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import services, tasks, techfile
from . import workflow as wf
from .access import (SESSION_DEVICE_KEY, accessible_devices, current_device, form_page,
                     qms_member, require_access, run, team_member)
from .forms import DeviceForm, OrganisationForm, SignForm, TeamMemberForm, TeamRolesForm
from .invitations import device_invitations
from .roles import can_manage_team, device_roles, org_roles
from .models import (AuditEvent, Device, DeviceMembership, Organisation, Signature, StageGate,
                     TechnicalFileBuild)


@qms_member
@require_POST
def set_device(request):
    """Header switcher: choose a device to focus on, or all devices."""
    device_id = request.POST.get("device", "")
    device = (accessible_devices(request.user).filter(pk=device_id, active=True).first()
              if device_id.isdigit() else None)
    if device:
        request.session[SESSION_DEVICE_KEY] = device.pk
        messages.info(request, f"Now working in the {device.name} QMS. Switch from Devices "
                               "in the top bar.")
    else:
        request.session.pop(SESSION_DEVICE_KEY, None)
        messages.info(request, "Now working across all your devices.")
    nxt = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(nxt, {request.get_host()}):
        nxt = reverse("qms:dashboard")
    return redirect(nxt)


@team_member
def device_list(request):
    """Your devices and your roles on each; opening one loads its QMS. Shown after sign-in,
    and from Devices in the top bar to switch to another device's QMS."""
    user = request.user
    labels = dict(wf.RECORD_TYPES)
    org = org_roles(user)
    current = current_device(request)
    rows = []
    for d in accessible_devices(user).order_by("-active", "name"):
        open_counts = Counter(labels[t] for t in d.records.exclude(
            status__in=wf.TERMINAL_STATES).values_list("record_type", flat=True))
        held = device_roles(user, d)
        rows.append({
            "device": d,
            "roles": [(r, r in org) for r in wf.ROLES if r in held],
            # Device admin alone manages the team but doesn't work in the QMS.
            "can_open": d.active and bool(held & set(wf.ANY_ROLE)),
            "current": current is not None and current.pk == d.pk,
            "open_counts": sorted(open_counts.items()),
            "approved": d.technical_files.filter(status="approved").first(),
        })
    return render(request, "qms/device_list.html", {
        "rows": rows, "current": current, "organisation": Organisation.current(),
        "can_open_all": sum(r["can_open"] for r in rows) > 1})


@qms_member
def device_create(request):
    if not services.user_has_role(request.user, [wf.QA]):
        messages.error(request, "Requires role: QA.")
        return redirect("qms:device_list")
    form = DeviceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        device = form.save(commit=False)
        device.save(_actor=request.user)
        creator = DeviceMembership(device=device, user=request.user, note="Created the device")
        creator.set_roles([wf.QA, wf.DEVICE_ADMIN])
        creator.save(_actor=request.user)
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
    if not services.user_has_role(request.user, [wf.QA], device):
        messages.error(request, f"Requires role: QA on {device.name}.")
        return redirect("qms:device_detail", code=code)
    form = DeviceForm(request.POST or None, instance=device)
    if request.method == "POST" and form.is_valid():
        d = form.save(commit=False)
        d.save(_actor=request.user)
        messages.success(request, "Saved.")
        return redirect("qms:device_detail", code=d.code)
    return form_page(request, form, f"Edit {device.name}",
                     reverse("qms:device_detail", args=[code]))


@team_member
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
        "is_qa": services.user_has_role(request.user, [wf.QA], device),
        "signatures": Signature.objects.filter(object_type="Technical File Build",
                                               object_ref__in=[b.label for b in builds]),
        "events": AuditEvent.objects.filter(
            Q(object_ref__in=[device.code] + [b.label for b in builds])
            | Q(object_type="Device Membership", object_ref__endswith=f"@ {device.code}"))
            .order_by("-id")[:50],
        "team": _team_rows(request.user, device),
        "team_form": TeamMemberForm(device=device),
        "can_manage_team": can_manage_team(request.user, device),
        "invitations": device_invitations(device) if can_manage_team(request.user, device)
        else [],
        "organisation": Organisation.current(),
    })


def _team_rows(viewer, device):
    """(membership, roles form, organisation-wide roles) for each member. The form is only
    there when the viewer may change that person's roles (never their own)."""
    from .roles import org_roles
    rows = []
    for m in device.memberships.filter(active=True).select_related("user"):
        editable = can_manage_team(viewer, device) and m.user_id != viewer.pk
        form = TeamRolesForm(initial={"roles": m.role_list(), "note": m.note},
                             prefix=f"m{m.pk}") if editable else None
        org = [r for r in wf.ROLES if r in org_roles(m.user) and not m.user.is_superuser]
        rows.append((m, form, org))
    return rows


def _managers_left(device, without=None, new_roles=None):
    """How many team members could still manage the team after removing ``without`` (or
    giving it ``new_roles``). Organisation-wide roles count too."""
    from .roles import org_roles
    count = 0
    for m in device.memberships.filter(active=True).select_related("user"):
        if without and m.pk == without.pk:
            if new_roles is None:
                continue
            roles = set(new_roles) | org_roles(m.user)
        else:
            roles = set(m.role_list()) | org_roles(m.user)
        if roles & set(wf.TEAM_MANAGERS):
            count += 1
    return count


@team_member
@require_POST
def team_add(request, code):
    device = get_object_or_404(Device, code=code)
    require_access(request, device)
    if not can_manage_team(request.user, device):
        messages.error(request, "Only Device admins and QA on this device can change its team.")
        return redirect("qms:device_detail", code=code)
    form = TeamMemberForm(request.POST, device=device)
    if form.is_valid():
        user = form.cleaned_data["user"]
        m = (DeviceMembership.objects.filter(device=device, user=user).first()
             or DeviceMembership(device=device, user=user))
        m.active = True
        m.note = form.cleaned_data["note"] or m.note
        m.set_roles(set(m.role_list()) | set(form.cleaned_data["roles"]))
        m.save(_actor=request.user, _comment="Added to team")
        services.sync_training()
        messages.success(request, f"{user.get_full_name() or user.username} added to the "
                                  f"{device.name} team as {', '.join(m.role_list())}.")
    else:
        messages.error(request, "Choose a person and at least one role.")
    return redirect("qms:device_detail", code=code)


@team_member
@require_POST
def team_roles(request, pk):
    m = get_object_or_404(DeviceMembership, pk=pk, active=True)
    require_access(request, m.device)
    form = TeamRolesForm(request.POST, prefix=f"m{m.pk}")
    if not can_manage_team(request.user, m.device):
        messages.error(request, "Only Device admins and QA on this device can change its team.")
    elif m.user_id == request.user.pk:
        messages.error(request, "You can't change your own roles. Ask another Device admin or QA.")
    elif not form.is_valid():
        messages.error(request, "Choose valid roles.")
    elif _managers_left(m.device, without=m, new_roles=form.cleaned_data["roles"]) == 0:
        messages.error(request, "A device needs at least one Device admin or QA on its team.")
    else:
        before = m.role_list()
        m.set_roles(form.cleaned_data["roles"])
        m.note = form.cleaned_data["note"]
        m.save(_actor=request.user, _comment="Roles changed")
        services.sync_training()
        name = m.user.get_full_name() or m.user.get_username()
        if before != m.role_list():
            messages.success(request, f"{name}'s roles on {m.device.name}: "
                                      f"{', '.join(m.role_list()) or 'none'}.")
        else:
            messages.success(request, "Saved.")
    return redirect("qms:device_detail", code=m.device.code)


@team_member
@require_POST
def team_remove(request, pk):
    m = get_object_or_404(DeviceMembership, pk=pk)
    require_access(request, m.device)
    if not can_manage_team(request.user, m.device):
        messages.error(request, "Only Device admins and QA on this device can change its team.")
    elif m.device.memberships.filter(active=True).count() == 1:
        messages.error(request, "A device needs at least one team member.")
    elif _managers_left(m.device, without=m) == 0:
        messages.error(request, "A device needs at least one Device admin or QA on its team.")
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


# --- the organisation and its economic operator roles -----------------------------------

def _can_edit_organisation(user) -> bool:
    """QA held organisation-wide (superusers hold every role): the profile applies to all
    devices, so a device-level role isn't enough."""
    return wf.QA in org_roles(user)


@team_member
def organisation_detail(request):
    org = Organisation.current()
    devices = accessible_devices(request.user).filter(active=True).order_by("name")
    return render(request, "qms/organisation.html", {
        "org": org, "devices": devices, "can_edit": _can_edit_organisation(request.user),
        "events": AuditEvent.objects.filter(object_type="Organisation").order_by("-id")[:20]
        if org else [],
    })


@team_member
def organisation_edit(request):
    if not _can_edit_organisation(request.user):
        messages.error(request, "Only QA held organisation-wide can change the organisation "
                                "profile. Ask an administrator.")
        return redirect("qms:organisation")
    org = Organisation.current()
    form = OrganisationForm(request.POST or None, instance=org)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.save(_actor=request.user)
        messages.success(request, "Organisation profile saved.")
        return redirect("qms:organisation")
    return form_page(request, form, "Organisation profile", reverse("qms:organisation"),
                     intro="The legal entity running this QMS and its roles under the EU MDR. "
                           "Each device then records which of these roles apply to it.")


@qms_member
def device_tasks(request, code):
    """The person's kanban for one device: to do, waiting on others, and done recently."""
    device = get_object_or_404(Device, code=code)
    if not device_roles(request.user, device):
        raise PermissionDenied
    board = tasks.board(request.user, device)
    lanes = tasks.gate_lanes(request.user, device, tasks.ensure_gates(device))
    columns = [
        ("todo", "To do", board["todo"], "Nothing needs your action on this device."),
        ("waiting", "Waiting on others", board["waiting"],
         "Nothing you started is waiting on others."),
        ("done", "Done recently", board["done"], "No signatures in the last 30 days."),
    ]
    return render(request, "qms/device_tasks.html",
                  {"device": device, "columns": columns, "gate_lanes": lanes,
                   "route_label": device.get_development_route_display()})


@qms_member
@require_POST
def gate_approve(request, pk):
    gate = get_object_or_404(StageGate, pk=pk)
    require_access(request, gate.device)
    run(request, tasks.approve_gate, gate, request.user,
        success=f"Stage {gate.stage} approved: {gate.name}.")
    return redirect("qms:device_tasks", code=gate.device.code)
