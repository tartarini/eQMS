from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from qms import roles

from . import activation
from .forms import ExternalIssueForm, RegistrationForm, ReportForm, TriageForm
from .links import PROVIDER_LABELS, parse_issue_url
from .models import ExternalIssue, PmsProfile, Report

KIND_TITLES = {
    "feedback": "Give feedback",
    "complaint": "Make a complaint",
    "vigilance": "Report a suspected incident or malfunction",
}


def is_qms_staff(user) -> bool:
    return roles.is_qms_admin(user) or bool(roles.unlensed_all_roles(user))


def _message(request, title, text, link=None):
    return render(request, "pms/message.html",
                  {"title": title, "text": text, "link": link})


def register(request):
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        user = User(username=d["username"], email=d["email"], first_name=d["full_name"],
                    is_active=False)
        user.set_password(d["password1"])
        user.save()
        PmsProfile.objects.create(user=user, user_type=d["user_type"],
                                  organisation=d["organisation"])
        link = request.build_absolute_uri(
            reverse("pms:activate", args=[activation.activation_token(user)]))
        send_mail(
            "Activate your SAMD_QMS surveillance account",
            f"Hello {d['full_name']},\n\nOpen this link to activate your account. It is valid "
            f"for {settings.QMS_PMS_ACTIVATION_DAYS} days and can be used once:\n\n{link}\n\n"
            "If you did not register, ignore this email.",
            settings.DEFAULT_FROM_EMAIL, [user.email])
        return redirect("pms:activation_sent")
    return render(request, "qms/form.html", {
        "form": form, "title": "Register for surveillance reporting",
        "intro": "Create an account to send feedback, complaints or reports about a device. "
                 "You will confirm your email address, then set up an authenticator app: "
                 "a second step, a code from the app, is required every time you sign in.",
        "submit_label": "Register", "cancel_url": reverse("login")})


def activation_sent(request):
    return _message(request, "Check your email",
                    "We have sent an activation link to your email address. Open it to "
                    "activate your account, then sign in.", link=reverse("login"))


def activate(request, token):
    user = activation.user_for_token(token)
    if user is None:
        return _message(request, "This link is not valid",
                        "The activation link is invalid, has expired, or was already used. "
                        "If you have activated your account, sign in. Otherwise register again.",
                        link=reverse("pms:register"))
    user.is_active = True
    user.save(update_fields=["is_active"])
    return _message(request, "Account activated",
                    "Your account is active. Sign in, then set up your authenticator app.",
                    link=reverse("login"))


@login_required
def report_list(request):
    reports = (Report.objects.filter(reporter=request.user)
               .select_related("device"))
    return render(request, "pms/report_list.html", {
        "reports": reports, "kinds": KIND_TITLES, "is_staff": is_qms_staff(request.user)})


@login_required
def report_new(request, kind):
    if kind not in KIND_TITLES:
        raise Http404
    form = ReportForm(request.POST or None, kind=kind)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.kind = kind
        report.reporter = request.user
        profile = PmsProfile.objects.filter(user=request.user).first()
        report.reporter_type = profile.user_type if profile else "qms_staff"
        report.save()
        messages.success(request, f"Thank you. Your reference is {report.number}.")
        return redirect("pms:report_detail", number=report.number)
    return render(request, "qms/form.html", {
        "form": form, "title": KIND_TITLES[kind],
        "intro": "Fields marked * are required. Describe the problem as you saw it; you do not "
                 "need to know the cause. Add a link to an existing issue at any time after "
                 "you send the report.",
        "submit_label": "Send", "cancel_url": reverse("pms:report_list")})


def _visible_report(request, number):
    report = get_object_or_404(Report.objects.select_related("device", "reporter"),
                               number=number)
    if report.reporter_id != request.user.pk and not is_qms_staff(request.user):
        raise Http404
    return report


@login_required
def report_detail(request, number):
    report = _visible_report(request, number)
    staff = is_qms_staff(request.user)
    return render(request, "pms/report_detail.html", {
        "report": report, "staff": staff,
        "issue_form": ExternalIssueForm(), "triage_form": TriageForm(initial={"status": report.status}),
        "issues": report.external_issues.all(), "providers": PROVIDER_LABELS})


@login_required
def report_link_add(request, number):
    report = _visible_report(request, number)
    if request.method != "POST":
        return redirect("pms:report_detail", number=report.number)
    form = ExternalIssueForm(request.POST)
    if form.is_valid():
        url = form.cleaned_data["url"]
        if report.external_issues.filter(url=url).exists():
            messages.info(request, "That issue is already linked to this report.")
        else:
            provider, reference = parse_issue_url(url)
            ExternalIssue.objects.create(report=report, url=url, provider=provider,
                                         reference=reference, added_by=request.user)
            messages.success(request, "Issue linked to this report.")
        return redirect("pms:report_detail", number=report.number)
    for error in form.errors.get("url", []):
        messages.error(request, error)
    return redirect("pms:report_detail", number=report.number)


@login_required
def triage_list(request):
    if not is_qms_staff(request.user):
        raise PermissionDenied
    reports = Report.objects.select_related("device", "reporter").order_by("-created_at")
    status = request.GET.get("status", "")
    if status in dict(Report.STATUSES):
        reports = reports.filter(status=status)
    return render(request, "pms/triage_list.html", {
        "reports": reports, "statuses": Report.STATUSES, "current_status": status})


@login_required
def triage_update(request, number):
    if not is_qms_staff(request.user):
        raise PermissionDenied
    report = get_object_or_404(Report, number=number)
    if request.method == "POST":
        form = TriageForm(request.POST)
        if form.is_valid():
            report.status = form.cleaned_data["status"]
            report.save()
            messages.success(request, f"{report.number} is now {report.get_status_display().lower()}.")
    return redirect("pms:report_detail", number=report.number)
