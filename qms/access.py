"""Access control and small helpers shared by the views."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from . import workflow as wf
from .models import ImmutableError


def is_member(user) -> bool:
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__in=wf.ANY_ROLE).exists())


def qms_member(view):
    """Signed in AND holding a QMS role. SSO accounts without a role see a holding page."""
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_member(request.user):
            return render(request, "qms/access_pending.html", status=403)
        return view(request, *args, **kwargs)
    return wrapped


def run(request, func, *args, success=None, **kwargs):
    """Run a service call; turn rule violations into on-page error messages."""
    from .services import TransitionError
    try:
        result = func(*args, **kwargs)
    except TransitionError as exc:
        for err in exc.errors:
            messages.error(request, err)
        return None
    except ImmutableError as exc:
        messages.error(request, str(exc))
        return None
    if success:
        messages.success(request, success)
    return result if result is not None else True


def form_page(request, form, title, cancel_url, intro=""):
    return render(request, "qms/form.html", {"form": form, "title": title,
                                             "cancel_url": cancel_url, "intro": intro})


# --- device teams and the current device ------------------------------------------

SESSION_DEVICE_KEY = "qms_device_id"


def sees_all_devices(user) -> bool:
    return user.is_superuser or user.groups.filter(name=wf.ALL_DEVICES).exists()


def accessible_devices(user):
    """Devices whose data this person may see: their teams, or all with All-device access."""
    from .models import Device
    if not user.is_authenticated:
        return Device.objects.none()
    if sees_all_devices(user):
        return Device.objects.all()
    return Device.objects.filter(memberships__user=user, memberships__active=True).distinct()


def can_access(user, device) -> bool:
    """None means QMS-wide (no device), which every QMS member can see."""
    if device is None:
        return True
    if sees_all_devices(user):
        return True
    return device.memberships.filter(user=user, active=True).exists()


def require_access(request, device):
    """Raise 404 (not 403, so other teams' references aren't revealed) if out of bounds."""
    if not can_access(request.user, device):
        raise Http404("Not found")


def current_device(request):
    """The device chosen in the header switcher, or None for all accessible devices."""
    device_id = request.session.get(SESSION_DEVICE_KEY)
    if not device_id:
        return None
    return accessible_devices(request.user).filter(pk=device_id, active=True).first()


def scope(queryset, request, field="device", allow_shared=False):
    """
    Limit a queryset to devices this person may see, and to the current device if one is
    chosen. ``allow_shared`` keeps rows with no device (QMS-wide documents, unlinked SOUP).
    """
    from django.db.models import Q
    device = current_device(request)
    allowed = [device] if device else accessible_devices(request.user)
    cond = Q(**{f"{field}__in": allowed})
    if allow_shared:
        cond |= Q(**{f"{field}__isnull": True})
    return queryset.filter(cond).distinct()
