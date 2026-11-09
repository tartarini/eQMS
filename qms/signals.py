"""Security and relationship events written to the audit trail."""
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils import timezone

from .models import AuditEvent, Record

User = get_user_model()


class _UserRef:
    """Lets AuditEvent.log attribute an event to a user account as its subject."""
    audit_type = "User"

    def __init__(self, username):
        self.audit_ref = username


def log_security(user_or_name, action_text, actor=None, **changes):
    name = user_or_name if isinstance(user_or_name, str) else user_or_name.get_username()
    AuditEvent.log("security", obj=_UserRef(name), actor=actor,
                   changes={"event": action_text, **changes})


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    method = "password"
    sociallogin = getattr(request, "_qms_sociallogin_provider", None)
    if sociallogin:
        method = sociallogin
    if request is not None and hasattr(request, "session"):
        request.session["qms_login_at"] = timezone.now().isoformat()
        request.session["qms_login_method"] = method
    log_security(user, "login", actor=user, method=method,
                 ip=(request.META.get("REMOTE_ADDR") if request else None))


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        log_security(user, "logout", actor=user)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    log_security(str(credentials.get("username", "unknown"))[:60], "login failed",
                 ip=(request.META.get("REMOTE_ADDR") if request else None))


@receiver(m2m_changed, sender=User.groups.through)
def on_roles_changed(sender, instance, action, pk_set, reverse, **kwargs):
    if action not in ("post_add", "post_remove", "post_clear") or reverse:
        return
    from django.contrib.auth.models import Group
    names = sorted(Group.objects.filter(pk__in=pk_set or []).values_list("name", flat=True))
    log_security(instance, "roles changed", op=action.replace("post_", ""), roles=names,
                 now=sorted(instance.groups.values_list("name", flat=True)))


@receiver(m2m_changed, sender=Record.hazards.through)
def on_record_hazards_changed(sender, instance, action, pk_set, reverse, **kwargs):
    if action not in ("post_add", "post_remove") or reverse:
        return
    from .models import Hazard
    refs = sorted(Hazard.objects.filter(pk__in=pk_set).values_list("ref", flat=True))
    AuditEvent.log("update", record=instance,
                   changes={"hazards": {"added" if action == "post_add" else "removed": refs}})


def _on_soup_devices_changed(sender, instance, action, pk_set, reverse, **kwargs):
    if action not in ("post_add", "post_remove") or reverse:
        return
    from .models import Device
    codes = sorted(Device.objects.filter(pk__in=pk_set).values_list("code", flat=True))
    AuditEvent.log("update", obj=instance,
                   changes={"devices": {"added" if action == "post_add" else "removed": codes}})


def _connect_late_signals():
    from .models import SoupItem
    m2m_changed.connect(_on_soup_devices_changed, sender=SoupItem.devices.through,
                        dispatch_uid="qms_soup_devices")


_connect_late_signals()


try:  # allauth signals: SSO-specific events
    from allauth.account.signals import user_signed_up
    from allauth.socialaccount.signals import (pre_social_login, social_account_added,
                                               social_account_removed)

    @receiver(pre_social_login)
    def on_pre_social_login(sender, request, sociallogin, **kwargs):
        request._qms_sociallogin_provider = f"sso:{sociallogin.account.provider}"

    @receiver(user_signed_up)
    def on_signed_up(sender, request, user, **kwargs):
        from . import notifications
        from .access_requests import captcha_passed
        if captcha_passed(request):
            # An account request: QA is emailed when the request itself is submitted.
            log_security(user, "account created via SSO for an account request", actor=user)
            return
        log_security(user, "account created via SSO", actor=user)
        notifications.user_awaiting_access(user)

    @receiver(social_account_added)
    def on_social_added(sender, request, sociallogin, **kwargs):
        log_security(sociallogin.user, "SSO account connected", actor=sociallogin.user,
                     provider=sociallogin.account.provider)

    @receiver(social_account_removed)
    def on_social_removed(sender, request, socialaccount, **kwargs):
        log_security(socialaccount.user, "SSO account disconnected", actor=socialaccount.user,
                     provider=socialaccount.provider)
except ImportError:  # pragma: no cover - allauth not installed
    pass
