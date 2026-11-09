from .help import PAGE_HELP, help_url
from .access import accessible_devices, current_device, is_member, sees_all_devices


def devices(request):
    """Device switcher data, and whether to show Invitations, for every page."""
    from .roles import managed_devices
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    data = {"manages_teams": bool(managed_devices(user))}
    if data["manages_teams"]:
        from .models import AccessRequest
        data["open_access_requests"] = AccessRequest.objects.filter(status="pending").count()
    if is_member(user):
        data.update({"all_devices": accessible_devices(user).filter(active=True),
                     "current_device": current_device(request),
                     "sees_all_devices": sees_all_devices(user)})
    return data


def page_help(request):
    """Link to the help section for the current page, shown in the header of every page."""
    match = getattr(request, "resolver_match", None)
    name = match.url_name if match else None
    if name in PAGE_HELP:
        topic, anchor = PAGE_HELP[name]
    elif name and name.startswith("socialaccount_"):
        topic, anchor = "getting-started", "connected-accounts"
    elif name and name.startswith("account_"):
        topic, anchor = "getting-started", "signing-in"
    else:
        topic, anchor = "", ""
    return {"page_help_url": help_url(topic, anchor)}


def release(request):
    """Version and commit for the top of every page; the copyright notice for its foot."""
    from django.conf import settings
    commit = settings.QMS_COMMIT
    return {"qms_version": settings.QMS_VERSION, "qms_commit": commit,
            "qms_commit_short": commit[:7] if commit != "unknown" else commit,
            "qms_copyright": settings.QMS_COPYRIGHT}


def admin_link(request):
    """Show the header's Admin link to staff only where admin answers (see admin_access)."""
    from .admin_access import admin_allowed
    user = getattr(request, "user", None)
    return {"show_admin_link": bool(user and user.is_authenticated and user.is_staff
                                    and admin_allowed(request))}
