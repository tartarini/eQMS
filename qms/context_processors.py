from .help import PAGE_HELP, help_url
from .access import accessible_devices, current_device, is_member, sees_all_devices


def devices(request):
    """Device switcher data for every page."""
    if not getattr(request, "user", None) or not is_member(request.user):
        return {}
    return {"all_devices": accessible_devices(request.user).filter(active=True),
            "current_device": current_device(request),
            "sees_all_devices": sees_all_devices(request.user)}


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
