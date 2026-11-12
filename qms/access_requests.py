"""
Account requests from the public landing page.

The route in, in order:
  1. The person solves the captcha on /request-access/. The session is marked for
     QMS_ACCESS_REQUEST_MINUTES.
  2. Within that time they register with single sign-on, using one of
     QMS_ACCESS_REQUEST_PROVIDERS (Google, Microsoft, LinkedIn, ORCID). Only then may single
     sign-on create an account outside the allowed domains (``qms.sso``). No local accounts.
  3. They fill in the request. If the provider did not give a verified email address (ORCID
     never does) they confirm one from an emailed link first.
  4. QA and anyone who manages a team are emailed. A Device admin or QA approves it by putting
     the person on a device team they manage, with roles; QA may decline it with a reason.

The new account has no role until approved, so it sees nothing but its own request.
Every step is in the audit trail.
"""
import time

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone

from . import notifications
from . import workflow as wf
from .models import AccessRequest, DeviceMembership
from .roles import can_manage_team, managed_devices, may_change_device_admin, org_roles
from .services import TransitionError, require

SESSION_KEY = "qms_access_request_started"
CONFIRM_SALT = "qms.access-request.confirm"


# --- step 1-2: captcha passed, so single sign-on may register this browser --------------

def mark_captcha_passed(request) -> None:
    request.session[SESSION_KEY] = int(time.time())


def captcha_passed(request) -> bool:
    started = request.session.get(SESSION_KEY) if request is not None else None
    return bool(started) and time.time() - started <= settings.QMS_ACCESS_REQUEST_MINUTES * 60


def provider_allowed(provider_id: str) -> bool:
    return provider_id in settings.QMS_ACCESS_REQUEST_PROVIDERS


def registration_providers(providers):
    """The configured providers people may register with, in the settings' order."""
    order = settings.QMS_ACCESS_REQUEST_PROVIDERS
    pid = lambda p: getattr(p, "sub_id", None) or p.id  # noqa: E731 - LinkedIn is an OIDC app
    return sorted((p for p in providers if pid(p) in order), key=lambda p: order.index(pid(p)))


# --- step 3: the request ------------------------------------------------------------------

def open_request(user):
    return AccessRequest.objects.filter(user=user, status__in=AccessRequest.OPEN).first()


def verified_email(user) -> str:
    from allauth.account.models import EmailAddress
    if not user.email:
        return ""
    ok = EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists()
    return user.email if ok else ""


def submit(request, user, data: dict) -> AccessRequest:
    """Creates the request. Emails a confirmation link unless the address is already verified."""
    errors = []
    require(errors, open_request(user) is None, "You already have a request waiting.")
    from .access import has_any_role
    require(errors, not has_any_role(user), "You already have access to SAMD_QMS.")
    if errors:
        raise TransitionError(errors)
    known = verified_email(user)
    email = known or data["email"].strip().lower()
    provider = user.socialaccount_set.order_by("-date_joined").values_list(
        "provider", flat=True).first() or ""
    with transaction.atomic():
        user.first_name, user.last_name = data["first_name"], data["last_name"]
        user.save(update_fields=["first_name", "last_name"])
        ar = AccessRequest(user=user, first_name=data["first_name"], last_name=data["last_name"],
                           email=email, email_verified=bool(known),
                           organisation=data["organisation"], position=data["position"],
                           devices=data["devices"], role=data["role"], reason=data["reason"],
                           provider=provider, status="pending" if known else "unconfirmed")
        if known:
            ar.confirmed_at = timezone.now()
        ar.save(_actor=user, _comment="Account requested")
    if request is not None:
        request.session.pop(SESSION_KEY, None)
    if known:
        notifications.access_requested(ar)
    else:
        send_confirmation(ar)
    return ar


def confirm_token(ar: AccessRequest) -> str:
    return signing.dumps({"r": ar.pk, "e": ar.email}, salt=CONFIRM_SALT)


def send_confirmation(ar: AccessRequest) -> None:
    from django.urls import reverse
    link = settings.QMS_BASE_URL.rstrip("/") + reverse("qms:access_request_confirm",
                                                       args=[confirm_token(ar)])
    notifications.access_confirm_email(ar, link)


def confirm(token: str):
    """Confirms the email address in a link. Returns the request, or None if the link is not
    valid, has expired, or the request has moved on."""
    try:
        data = signing.loads(token, salt=CONFIRM_SALT,
                             max_age=settings.QMS_ACCESS_CONFIRM_DAYS * 86400)
    except signing.BadSignature:
        return None
    ar = AccessRequest.objects.filter(pk=data.get("r"), email=data.get("e")).first()
    if ar is None or ar.status not in AccessRequest.OPEN:
        return None
    if ar.status == "unconfirmed":
        from allauth.account.models import EmailAddress
        with transaction.atomic():
            ar.email_verified, ar.status, ar.confirmed_at = True, "pending", timezone.now()
            ar.save(_actor=ar.user, _comment="Email address confirmed")
            user = ar.user
            if not user.email:
                user.email = ar.email
                user.save(update_fields=["email"])
            EmailAddress.objects.update_or_create(
                user=user, email=ar.email, defaults={"verified": True,
                                                     "primary": user.email == ar.email})
        notifications.access_requested(ar)
    return ar


# --- step 4: review -----------------------------------------------------------------------

def can_review(user) -> bool:
    """Device admins and QA on any device (they approve onto their own devices)."""
    return bool(managed_devices(user))


def can_decline(user) -> bool:
    from .roles import all_roles
    return user.is_superuser or wf.QA in all_roles(user) or wf.QA in org_roles(user)


def approve(ar: AccessRequest, approver, device, roles, note: str = "") -> AccessRequest:
    errors = []
    require(errors, ar.status == "pending", f"{ar.ref} is not waiting for review.")
    require(errors, can_manage_team(approver, device),
            f"Only Device admins and QA on {device.name} can add people to its team.")
    require(errors, bool(roles), "Choose at least one role.")
    require(errors, may_change_device_admin(approver, set(), roles),
            "Only a QMS admin can approve someone as a Device admin.")
    require(errors, approver.pk != ar.user_id, "You can't approve your own request.")
    if errors:
        raise TransitionError(errors)
    from . import services
    with transaction.atomic():
        m = (DeviceMembership.objects.filter(device=device, user=ar.user).first()
             or DeviceMembership(device=device, user=ar.user))
        m.active = True
        m.set_roles(set(m.role_list()) | set(roles))
        m.save(_actor=approver, _comment=f"Added to team: {ar.ref} approved")
        ar.status, ar.decided_by, ar.decided_at = "approved", approver, timezone.now()
        ar.decision_note = note
        ar.grants = [{"device_id": device.pk, "device": device.code, "roles": m.role_list()}]
        ar.save(_actor=approver, _comment="Account request approved")
    services.sync_training()
    notifications.access_decided(ar)
    return ar


def decline(ar: AccessRequest, approver, reason: str) -> AccessRequest:
    errors = []
    require(errors, ar.is_open, f"{ar.ref} has already been decided.")
    require(errors, can_decline(approver), "Only QA can decline account requests.")
    require(errors, bool((reason or "").strip()), "Give a reason: it is sent to the person.")
    if errors:
        raise TransitionError(errors)
    ar.status, ar.decided_by, ar.decided_at = "declined", approver, timezone.now()
    ar.decision_note = reason.strip()
    ar.save(_actor=approver, _comment="Account request declined")
    notifications.access_decided(ar)
    return ar
