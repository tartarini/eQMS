"""Inviting people by email, and the page the emailed link opens."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import invitations
from .access import run, team_member
from .forms import InvitationForm
from .models import Device, Invitation
from .roles import managed_devices


@team_member
def invitation_list(request):
    visible = invitations.visible_invitations(request.user)
    return render(request, "qms/invitation_list.html", {
        "open": [i for i in visible if i.state in ("pending", "expired")],
        "closed": [i for i in visible if i.state in ("accepted", "revoked")][:100],
        "can_invite": bool(managed_devices(request.user)),
        "can_administer": {i.pk for i in visible if invitations.can_administer(request.user, i)},
    })


@team_member
def invitation_create(request):
    devices = managed_devices(request.user)
    if not devices:
        messages.error(request, "Only Device admins and QA can invite people, to the devices "
                                "whose team they manage.")
        return redirect("qms:device_list")
    first = Device.objects.filter(code=request.GET.get("device", "")).first()
    form = InvitationForm(request.POST or None, devices=devices, first=first)
    if request.method == "POST" and form.is_valid():
        result = run(request, invitations.create_invitation, request.user,
                     form.cleaned_data["email"], form.grants(),
                     form.cleaned_data["expires_in_days"], form.cleaned_data["message"])
        if result:
            invitation, _token = result
            messages.success(request, f"Invitation sent to {invitation.email}. The link expires "
                                      f"on {invitation.expires_at:%d %b %Y}.")
            if first:
                return redirect("qms:device_detail", code=first.code)
            return redirect("qms:invitation_list")
    return render(request, "qms/form.html", {
        "form": form, "title": "Invite people",
        "cancel_url": reverse("qms:device_detail", args=[first.code]) if first
        else reverse("qms:invitation_list"),
        "intro": "They'll get an email with a link to create an account or sign in. Choose "
                 "their roles on each device; leave a device blank to leave them off its team. "
                 "You can only grant roles on devices whose team you manage.",
        "submit_label": "Send invitation",
    })


@team_member
@require_POST
def invitation_revoke(request, pk):
    invitation = get_object_or_404(Invitation, pk=pk)
    run(request, invitations.revoke, invitation, request.user,
        success=f"{invitation.ref} to {invitation.email} revoked. Its link no longer works.")
    return redirect("qms:invitation_list")


@team_member
@require_POST
def invitation_resend(request, pk):
    invitation = get_object_or_404(Invitation, pk=pk)
    if run(request, invitations.resend, invitation, request.user):
        messages.success(request, f"{invitation.ref} sent again to {invitation.email} with a new "
                                  f"link, expiring on {invitation.expires_at:%d %b %Y}. The "
                                  "previous link no longer works.")
    return redirect("qms:invitation_list")


def invitation_accept(request, token):
    """Open to anyone with the link: shows the invitation and lets the person accept it by
    signing in to an existing account or registering with single sign-on."""
    invitation = invitations.find(token)
    context = {"invitation": invitation, "token": token}
    if invitation is None:
        return render(request, "qms/invitation_accept.html", {**context, "state": "invalid"},
                      status=404)
    context["state"] = state = invitation.state
    if state != "pending":
        return render(request, "qms/invitation_accept.html", context, status=410)
    # Remembered so that single sign-on may create an account for the invited address.
    request.session["qms_invitation_token"] = token
    context["grants"] = [(Device.objects.get(pk=g["device_id"]), g["roles"])
                         for g in invitation.grants]

    if request.user.is_authenticated:
        context["errors"] = invitations.acceptance_errors(invitation, request.user)
        if request.method == "POST" and not context["errors"]:
            if run(request, invitations.accept, invitation, request.user):
                return _welcome(request, invitation)
            context["errors"] = invitations.acceptance_errors(invitation, request.user)
        return render(request, "qms/invitation_accept.html", context)

    # Signed out: a new person registers only with single sign-on (no local username and
    # password); sso.SocialAccountAdapter allows it for the invited, provider-verified address.
    context["has_account"] = get_user_model().objects.filter(
        email__iexact=invitation.email, is_active=True).exists()
    context["providers"] = invitations.signup_providers(request)
    return render(request, "qms/invitation_accept.html", context)


def _welcome(request, invitation):
    request.session.pop("qms_invitation_token", None)
    invitation.refresh_from_db()
    codes = ", ".join(code for code, _ in invitation.grant_lines())
    messages.success(request, f"Welcome to SAMD_QMS. You're now on the {codes} team(s).")
    if invitation.grants:
        device = Device.objects.filter(pk=invitation.grants[0]["device_id"]).first()
        if device:
            return redirect("qms:device_detail", code=device.code)
    return redirect("qms:dashboard")
