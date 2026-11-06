"""Who holds which role, where.

Roles are held per device: a person's team membership on a device lists their roles there
(``DeviceMembership.roles``), so someone can be QA on one device and an Engineer on another.

Organisation-wide roles are the ``auth.Group`` of the same name, set by an administrator in
Admin (for example a head of quality). An organisation-wide role applies on every device the
person can see: their teams, or every device with All-device access.

QMS-wide items (documents with no device, suppliers, training requirements on them) belong to
no device, so a role counts if it is held organisation-wide or on any device.

Superusers hold every role. Every role check in the app goes through ``has_role``.
"""
from django.contrib.auth import get_user_model

from . import workflow as wf


def org_roles(user) -> set:
    """Organisation-wide roles (Admin groups), applying on every device the person can see."""
    if not (user and user.is_authenticated and user.is_active):
        return set()
    if user.is_superuser:
        return set(wf.ROLES)
    return set(user.groups.filter(name__in=wf.ROLES).values_list("name", flat=True))


def _memberships(user, device=None):
    from .models import DeviceMembership
    qs = DeviceMembership.objects.filter(user=user, active=True, device__active=True)
    return qs.filter(device=device) if device is not None else qs


def device_roles(user, device) -> set:
    """Roles on one device; for ``None`` (QMS-wide items) roles held anywhere."""
    from .access import can_access
    if not (user and user.is_authenticated and user.is_active):
        return set()
    if device is None:
        return all_roles(user)
    if not can_access(user, device):
        return set()
    held = org_roles(user)
    for m in _memberships(user, device):
        held |= set(m.role_list())
    return held


def all_roles(user) -> set:
    """Every role the person holds, organisation-wide or on any device."""
    if not (user and user.is_authenticated and user.is_active):
        return set()
    held = org_roles(user)
    for m in _memberships(user):
        held |= set(m.role_list())
    return held


def has_role(user, roles, device=None) -> bool:
    """True if the person holds any of ``roles`` on ``device`` (None: QMS-wide)."""
    return bool(device_roles(user, device) & set(roles))


def roles_by_device(user) -> list:
    """(device, roles on it) for each device whose team the person is on."""
    return [(m.device, m.role_list()) for m in _memberships(user).select_related("device")]


def users_with_roles(roles, device=None) -> list:
    """Active people holding any of ``roles`` on ``device`` (None: anywhere)."""
    from .models import DeviceMembership
    User = get_user_model()
    roles = set(roles)
    candidates = set(User.objects.filter(is_active=True, groups__name__in=roles).values_list("pk", flat=True))
    members = DeviceMembership.objects.filter(active=True, device__active=True,
                                              user__is_active=True)
    if device is not None:
        members = members.filter(device=device)
    for m in members.only("user_id", "roles"):
        if roles & set(m.role_list()):
            candidates.add(m.user_id)
    users = User.objects.filter(pk__in=candidates).order_by("username")
    return [u for u in users if has_role(u, roles, device)]


def can_manage_team(user, device) -> bool:
    """Device admins and QA on the device (or organisation-wide) invite people and manage
    its team."""
    return has_role(user, wf.TEAM_MANAGERS, device)


def managed_devices(user):
    """Active devices whose team this person may manage."""
    from .access import accessible_devices
    return [d for d in accessible_devices(user).filter(active=True).order_by("name")
            if can_manage_team(user, d)]
