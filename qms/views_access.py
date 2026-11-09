"""The public landing page, and account requests (captcha, single sign-on, review)."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import access_requests as ar_service
from . import captcha
from .access import has_any_role, run, team_member
from .forms import AccessApproveForm, AccessDeclineForm, AccessRequestForm
from .models import AccessRequest
from .roles import managed_devices


def landing(request):
    """What SAMD_QMS is for, with the ways in. Shown at / to people who aren't signed in."""
    return render(request, "qms/landing.html")


def access_request(request):
    """Step 1: the captcha. Step 2: register with one of the allowed single sign-on providers."""
    if request.user.is_authenticated:
        return redirect("qms:access_request_details")
    if request.method == "POST":
        if captcha.verify(request):
            ar_service.mark_captcha_passed(request)
            return redirect("qms:access_request")
        messages.error(request, "The check didn't complete. Please try again.")
    context = {"passed": ar_service.captcha_passed(request), "backend": captcha.backend()}
    if context["passed"]:
        from allauth.socialaccount.adapter import get_adapter
        context.update({
            "providers": ar_service.registration_providers(get_adapter().list_providers(request)),
            "minutes": settings.QMS_ACCESS_REQUEST_MINUTES,
            "details_url": reverse("qms:access_request_details")})
    else:
        if context["backend"] == "pow":
            context["challenge"] = captcha.new_challenge(request)
        else:
            context["site_key"] = settings.QMS_TURNSTILE_SITE_KEY
    return render(request, "qms/access_request.html", context)


@login_required
def access_request_details(request):
    """Step 3: who you are and what you need. Also shows the state of an open request."""
    user = request.user
    if has_any_role(user):
        messages.info(request, "You already have access to SAMD_QMS.")
        return redirect("qms:dashboard")
    existing = ar_service.open_request(user)
    if existing:
        return render(request, "qms/access_request_status.html", {
            "ar": existing, "confirm_days": settings.QMS_ACCESS_CONFIRM_DAYS})
    known = ar_service.verified_email(user)
    form = AccessRequestForm(request.POST or None, known_email=known, initial={
        "first_name": user.first_name, "last_name": user.last_name})
    if request.method == "POST" and form.is_valid():
        ar = run(request, ar_service.submit, request, user, form.cleaned_data)
        if ar:
            return redirect("qms:access_request_details")
    return render(request, "qms/access_request_details.html", {"form": form, "known": known})


def access_request_confirm(request, token):
    """The emailed link: confirms the address and sends the request for review."""
    ar = ar_service.confirm(token)
    if ar is None:
        return render(request, "qms/access_request_status.html", {"invalid": True}, status=410)
    return render(request, "qms/access_request_status.html", {"ar": ar, "confirmed": True})


@team_member
def access_request_list(request):
    if not ar_service.can_review(request.user):
        messages.error(request, "Only Device admins and QA can review account requests.")
        return redirect("qms:dashboard")
    devices = managed_devices(request.user)
    items = AccessRequest.objects.select_related("user", "decided_by")
    open_items = list(items.filter(status__in=AccessRequest.OPEN))
    return render(request, "qms/access_request_list.html", {
        "open": [(a, AccessApproveForm(devices=devices, prefix=f"a{a.pk}")
                  if a.status == "pending" else None) for a in open_items],
        "closed": items.exclude(status__in=AccessRequest.OPEN)[:100],
        "decline_form": AccessDeclineForm(),
        "can_decline": ar_service.can_decline(request.user),
    })


@team_member
@require_POST
def access_request_approve(request, pk):
    ar = get_object_or_404(AccessRequest, pk=pk)
    form = AccessApproveForm(request.POST, devices=managed_devices(request.user),
                             prefix=f"a{ar.pk}")
    if form.is_valid():
        d = form.cleaned_data
        run(request, ar_service.approve, ar, request.user, d["device"], d["roles"], d["note"],
            success=f"{ar.ref} approved: {ar.full_name} is on the {d['device'].name} team.")
    else:
        messages.error(request, "Choose a device team you manage and at least one role.")
    return redirect(reverse("qms:access_request_list"))


@team_member
@require_POST
def access_request_decline(request, pk):
    ar = get_object_or_404(AccessRequest, pk=pk)
    form = AccessDeclineForm(request.POST)
    reason = form.cleaned_data["reason"] if form.is_valid() else ""
    run(request, ar_service.decline, ar, request.user, reason,
        success=f"{ar.ref} declined; {ar.full_name} has been emailed the reason.")
    return redirect("qms:access_request_list")
