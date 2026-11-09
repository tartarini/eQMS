"""Inviting people: Device admins and QA invite an email address to one or more device teams,
with roles on each. The person registers with single sign-on (or signs in to an existing
account) from the emailed link before it expires.

Rules:
  * No local username and password from an invitation: a new person registers only with a
    single sign-on provider that verifies the invited email address (not ORCID).
  * You can only grant roles on devices whose team you manage (Device admin or QA there).
  * The link is single use and expires (QMS_INVITATION_DAYS by default, at most
    QMS_INVITATION_MAX_DAYS). Only the token's SHA-256 is stored.
  * It must be accepted by an account whose email address is the invited one.
  * On acceptance, grants are re-checked: a grant from someone who can no longer manage that
    device's team is not applied.
  * Accepting adds roles; it never removes roles someone already has.
  * Every invitation, resend, revocation and acceptance is in the audit trail.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from . import notifications
from . import workflow as wf
from .models import Device, DeviceMembership, Invitation
from .roles import can_manage_team, managed_devices
from .services import TransitionError, require


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_token() -> tuple:
    token = secrets.token_urlsafe(32)
    return token, _hash(token)


def accept_url(token: str) -> str:
    return settings.QMS_BASE_URL.rstrip("/") + reverse("qms:invitation_accept", args=[token])


def find(token: str):
    """The invitation for a link's token, or None. Constant work whatever the token."""
    if not token or len(token) > 100:
        return None
    return Invitation.objects.filter(token_hash=_hash(token)).first()


def create_invitation(inviter, email: str, grants: dict, days: int = None, message: str = ""):
    """``grants``: {Device: [roles]}. Returns (invitation, token); emails the link."""
    days = days or settings.QMS_INVITATION_DAYS
    email = (email or "").strip().lower()
    errors = []
    try:
        validate_email(email)
    except ValidationError:
        errors.append("Enter a valid email address.")
    grants = {d: [r for r in wf.ROLES if r in set(roles)] for d, roles in grants.items() if roles}
    require(errors, bool(grants), "Choose at least one role on at least one device.")
    for device, roles in grants.items():
        require(errors, device.active, f"{device.name} is retired.")
        require(errors, can_manage_team(inviter, device),
                f"You can't invite people to {device.name}: only its Device admins and QA can.")
    require(errors, 1 <= days <= settings.QMS_INVITATION_MAX_DAYS,
            f"Choose an expiry between 1 and {settings.QMS_INVITATION_MAX_DAYS} days.")
    pending = [i for i in Invitation.objects.filter(email=email, status="pending")
               if not i.is_expired and set(i.device_ids()) & {d.pk for d in grants}]
    require(errors, not pending,
            f"{email} already has a pending invitation to "
            + ", ".join(sorted({c for i in pending for c, _ in i.grant_lines()}))
            + ". Resend or revoke it instead.")
    if errors:
        raise TransitionError(errors)
    token, token_hash = _new_token()
    with transaction.atomic():
        invitation = Invitation(
            email=email, token_hash=token_hash, message=message.strip(), invited_by=inviter,
            grants=[{"device_id": d.pk, "device": d.code, "roles": roles}
                    for d, roles in sorted(grants.items(), key=lambda kv: kv[0].name)],
            expires_at=timezone.now() + timedelta(days=days), last_sent_at=timezone.now())
        invitation.save(_actor=inviter, _comment="Invitation sent")
        notifications.invitation(invitation, accept_url(token))
    return invitation, token


def can_administer(user, invitation) -> bool:
    """The inviter, or anyone who manages every device in it, may resend or revoke it."""
    if invitation.invited_by_id == user.pk:
        return True
    devices = Device.objects.filter(pk__in=invitation.device_ids())
    return bool(devices) and all(can_manage_team(user, d) for d in devices)


def revoke(invitation, user):
    errors = []
    require(errors, can_administer(user, invitation),
            "Only the person who sent it, or a Device admin or QA on all its devices, can "
            "revoke it.")
    require(errors, invitation.state in ("pending", "expired"),
            f"{invitation.ref} is already {invitation.state}.")
    if errors:
        raise TransitionError(errors)
    invitation.status = "revoked"
    invitation.save(_actor=user, _comment="Invitation revoked")
    return invitation


def resend(invitation, user, days: int = None):
    """New link (the old one stops working) and a fresh expiry; emails it again."""
    errors = []
    require(errors, can_administer(user, invitation),
            "Only the person who sent it, or a Device admin or QA on all its devices, can "
            "resend it.")
    require(errors, invitation.state in ("pending", "expired"),
            f"{invitation.ref} is {invitation.state} and can't be resent.")
    if errors:
        raise TransitionError(errors)
    token, token_hash = _new_token()
    invitation.token_hash = token_hash
    invitation.expires_at = timezone.now() + timedelta(days=days or settings.QMS_INVITATION_DAYS)
    invitation.last_sent_at = timezone.now()
    with transaction.atomic():
        invitation.save(_actor=user, _comment="Invitation resent with a new link")
        notifications.invitation(invitation, accept_url(token))
    return invitation, token


def user_emails(user) -> set:
    """The account's email and any verified addresses from single sign-on."""
    emails = {user.email.lower()} if user.email else set()
    try:
        from allauth.account.models import EmailAddress
        emails |= {e.lower() for e in EmailAddress.objects.filter(user=user, verified=True)
                   .values_list("email", flat=True)}
    except Exception:  # noqa: BLE001 - allauth not installed
        pass
    return emails


def acceptance_errors(invitation, user) -> list:
    errors = []
    state = invitation.state
    if state != "pending":
        return [{"expired": "This invitation has expired. Ask the person who invited you to "
                            "send it again.",
                 "accepted": "This invitation has already been used.",
                 "revoked": "This invitation was withdrawn."}[state]]
    require(errors, invitation.email.lower() in user_emails(user),
            f"This invitation is for {invitation.email}, but you're signed in as "
            f"{user.get_username()} ({user.email or 'no email'}).")
    if not errors and not valid_grants(invitation):
        errors.append("This invitation is no longer valid: the person who sent it can no longer "
                      "add people to those devices. Ask them, or another Device admin, to "
                      "invite you again.")
    return errors


def valid_grants(invitation) -> list:
    """(device, roles) still grantable: device active and the inviter still manages its team."""
    out = []
    devices = {d.pk: d for d in Device.objects.filter(pk__in=invitation.device_ids(),
                                                      active=True)}
    for g in invitation.grants:
        device = devices.get(g["device_id"])
        if device and can_manage_team(invitation.invited_by, device):
            out.append((device, [r for r in g["roles"] if r in wf.ROLES]))
    return out


def accept(invitation, user) -> list:
    """Put the person on each team with the granted roles. Returns the (device, roles) applied."""
    errors = acceptance_errors(invitation, user)
    if errors:
        raise TransitionError(errors)
    applied = valid_grants(invitation)
    with transaction.atomic():
        invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
        if invitation.status != "pending":  # accepted twice at once
            raise TransitionError("This invitation has already been used.")
        for device, roles in applied:
            m = (DeviceMembership.objects.filter(device=device, user=user).first()
                 or DeviceMembership(device=device, user=user))
            m.active = True
            m.set_roles(set(m.role_list()) | set(roles))
            m.save(_actor=user, _comment=f"Joined through {invitation.ref} from "
                                         f"{invitation.invited_by.get_username()}")
        invitation.status = "accepted"
        invitation.accepted_by = user
        invitation.accepted_at = timezone.now()
        invitation.save(_actor=user, _comment="Invitation accepted")
    from .services import sync_training
    sync_training()
    return applied


def device_invitations(device):
    """Open invitations (pending or expired) that include this device."""
    return [i for i in Invitation.objects.filter(status="pending").select_related("invited_by")
            if device.pk in i.device_ids()]


def visible_invitations(user):
    """Invitations the person sent, or that include a device whose team they manage."""
    managed = {d.pk for d in managed_devices(user)}
    return [i for i in Invitation.objects.select_related("invited_by", "accepted_by")
            if i.invited_by_id == user.pk or managed & set(i.device_ids())]


def signup_providers(request):
    """Configured single sign-on providers an invited person can register with: those that
    report a verified email address, which must be the invited one (so not ORCID)."""
    from allauth.socialaccount.adapter import get_adapter
    return [p for p in get_adapter().list_providers(request) if p.id != "orcid"]


def pending_for_session(request):
    """The invitation whose link this browser opened, for allowing SSO sign-up."""
    token = request.session.get("qms_invitation_token") if request is not None else None
    invitation = find(token) if token else None
    return invitation if invitation and invitation.state == "pending" else None
