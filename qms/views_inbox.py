"""The inbox: the notifications sent to the signed-in person. Everyone sees their own only."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notification


def _unread(user):
    return Notification.objects.filter(recipient=user, read_at__isnull=True)


@login_required
def notification_list(request):
    items = Notification.objects.filter(recipient=request.user)[:200]
    return render(request, "qms/notification_list.html", {
        "items": items, "unread": _unread(request.user).count()})


@login_required
def notification_open(request, pk):
    """Mark one notification read and go to the page it is about."""
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if n.read_at is None:
        n.read_at = timezone.now()
        n.save(update_fields=["read_at"])
    # Only paths inside the app: never a link to another site.
    if n.path.startswith("/") and not n.path.startswith("//"):
        return redirect(n.path)
    return redirect("qms:notification_list")


@login_required
@require_POST
def notification_read_all(request):
    _unread(request.user).update(read_at=timezone.now())
    return redirect("qms:notification_list")
