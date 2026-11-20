from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from qms.models import Device

from .links import parse_issue_url
from .models import PmsProfile, Report


class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=150, label="Your name",
                                help_text="As you would like us to address you.")
    email = forms.EmailField(help_text="We send the activation link here.")
    username = forms.CharField(max_length=150,
                               help_text="The name you will sign in with.")
    user_type = forms.ChoiceField(choices=PmsProfile.USER_TYPES, label="I am a",
                                  help_text="Clinician, patient, carer or other end user.")
    organisation = forms.CharField(
        max_length=120, required=False, label="Hospital, clinic or organisation",
        help_text="Where you use the device, if that applies to you.")
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password",
                                help_text="At least 12 characters, not a common password.")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Repeat the password",
                                help_text="Type the same password again.")
    consent = forms.BooleanField(
        label="I understand what happens to my reports",
        help_text="Reports are kept as post-market surveillance records for the life of the "
                  "device. QMS staff see your name with your report, for traceability. We "
                  "contact you only if you ask us to.")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("That username is taken. Choose another.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists. "
                                  "Sign in, or use Forgotten password.")
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords do not match.")
        if p1:
            try:
                validate_password(p1, user=User(username=data.get("username", ""),
                                                email=data.get("email", "")))
            except ValidationError as err:
                self.add_error("password1", err)
        return data


class ReportForm(forms.ModelForm):
    """One form for all three kinds. The kind decides which fields are required."""

    class Meta:
        model = Report
        fields = ["device", "title", "description", "occurred_on", "aware_on", "software_version",
                  "environment", "steps", "harm", "contact_ok"]
        labels = {"device": "Device", "title": "Summary",
                  "description": "Describe what happened or what you think"}
        widgets = {"description": forms.Textarea(attrs={"rows": 6}),
                   "steps": forms.Textarea(attrs={"rows": 3}),
                   "occurred_on": forms.DateInput(attrs={"type": "date"}),
                   "aware_on": forms.DateInput(attrs={"type": "date"})}
        help_texts = {"title": "A short summary, in your own words.",
                      "description": "What you saw, what you expected, and what effect it had."}

    def __init__(self, *args, kind, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        self.fields["device"].queryset = Device.objects.order_by("name")
        self.fields["device"].empty_label = "Choose the device"
        self.fields["harm"].required = False
        self.fields["harm"].choices = [("", "Choose")] + list(Report.HARM)
        if kind == "feedback":
            self.fields["description"].label = "Your feedback"
            self.fields["harm"].widget = forms.HiddenInput()
        if kind in ("complaint", "vigilance"):
            self.fields["harm"].required = True
        if kind == "vigilance":
            self.fields["occurred_on"].required = True
            self.fields["aware_on"].required = True
            self.fields["description"].label = "What happened"
            self.fields["title"].label = "Summary of the problem"

    def clean(self):
        data = super().clean()
        if self.kind == "feedback":
            data["harm"] = "none"
        return data


class ExternalIssueForm(forms.Form):
    url = forms.URLField(
        max_length=500, label="Link to the issue",
        help_text="Paste the address of an issue already raised for this problem, for example "
                  "https://github.com/owner/repo/issues/12.")

    def clean_url(self):
        url = self.cleaned_data["url"].strip()
        try:
            parse_issue_url(url)
        except ValueError as err:
            raise ValidationError(str(err))
        return url


class TriageForm(forms.Form):
    status = forms.ChoiceField(choices=Report.STATUSES, label="Status",
                               help_text="Where this report is in the QMS process.")
