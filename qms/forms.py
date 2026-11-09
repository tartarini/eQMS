import os

from django import forms
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.validators import MaxValueValidator

from . import workflow as wf
from .models import (Attachment, Device, Document, DocumentVersion, Hazard, Record,
                     RecordLink, RiskControl, SoupItem, Supplier)

DATE_FIELDS = {"date_aware", "effectiveness_due", "due_date", "period_start", "period_end",
               "last_anomaly_review"}
TEXTAREAS = {"description", "investigation_summary", "root_cause", "impact_analysis",
             "resolution", "reportability_rationale", "change_summary", "hazard", "cause",
             "hazardous_situation", "harm", "benefit_risk_rationale", "scope", "notes",
             "purpose", "known_anomalies", "intended_purpose", "intended_users",
             "patient_population", "contraindications", "classification_rule", "manufacturer",
             "uk_responsible_person", "standards_applied", "software_items"}


def _widgets(field_names):
    widgets = {}
    for name in field_names:
        if name in DATE_FIELDS:
            widgets[name] = forms.DateInput(attrs={"type": "date"})
        elif name in TEXTAREAS:
            widgets[name] = forms.Textarea(attrs={"rows": 3})
    if "hazards" in field_names:
        widgets["hazards"] = forms.SelectMultiple(attrs={"size": 6})
    return widgets


class SoftwareItemInput(forms.TextInput):
    """Text box that suggests the software items of the devices on offer (HTML datalist)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.suggestions = []  # (item, device code)

    def render(self, name, value, attrs=None, renderer=None):
        from django.utils.html import format_html, format_html_join
        list_id = f"{(attrs or {}).get('id') or 'id_' + name}_options"
        attrs = {**(attrs or {}), "list": list_id, "autocomplete": "off"}
        html = super().render(name, value, attrs, renderer)
        options = format_html_join("", '<option value="{}">{}</option>', self.suggestions)
        return format_html('{}<datalist id="{}">{}</datalist>', html, list_id, options)


class DeviceScopedForm:
    """Mixin: limits device-linked choices to the devices this person can access, and checks
    that a software item is one of its device's items."""

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        devices = Device.objects.filter(active=True)
        if user is not None:
            from .access import accessible_devices
            devices = accessible_devices(user)
            for name, field in self.fields.items():
                model = getattr(getattr(field, "queryset", None), "model", None)
                if model is Device:
                    field.queryset = field.queryset.filter(pk__in=devices)
                elif model is Hazard:
                    field.queryset = field.queryset.filter(device__in=devices)
                elif model is Record:
                    field.queryset = field.queryset.filter(device__in=devices)
        if "software_item" in self.fields:
            widget = SoftwareItemInput()
            widget.suggestions = [(item, d.code) for d in devices.order_by("code")
                                  for item in d.software_item_list()]
            self.fields["software_item"].widget = widget

    def _chosen_devices(self, data):
        if data.get("device"):
            return [data["device"]]
        if data.get("devices") is not None:
            return list(data["devices"])
        device = getattr(self.instance, "device", None) if hasattr(self, "instance") else None
        return [device] if device else []

    def clean(self):
        data = super().clean()
        item = (data.get("software_item") or "").strip()
        if "software_item" in self.fields and item:
            allowed = [i for d in self._chosen_devices(data) for i in d.software_item_list()]
            if allowed:
                match = next((i for i in allowed if i.lower() == item.lower()), None)
                if match is None:
                    self.add_error("software_item", "Choose one of the device's software items: "
                                   + ", ".join(allowed) + ".")
                else:
                    data["software_item"] = match
        return data


class RecordFormBase(DeviceScopedForm, forms.ModelForm):
    def clean(self):
        data = super().clean()
        device = data.get("device")
        hazards = data.get("hazards")
        if device and hazards:
            wrong = [h.ref for h in hazards if h.device_id != device.pk]
            if wrong:
                self.add_error("hazards", f"{', '.join(wrong)} belong(s) to another device.")
        return data


def record_form_class(record_type: str):
    field_names = ["device", "title", "description", "owner"] + wf.TYPE_FIELDS[record_type]
    form = forms.modelform_factory(Record, form=RecordFormBase, fields=field_names,
                                   widgets=_widgets(field_names))
    form.base_fields["device"].queryset = Device.objects.filter(active=True)
    return form


class SignForm(forms.Form):
    comment = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    password = forms.CharField(
        label="Password or signing PIN", widget=forms.PasswordInput, required=False,
        help_text="Re-enter your password (or signing PIN) to apply your electronic signature.")


TransitionForm = SignForm


class LinkForm(forms.Form):  # noqa: D101 - target access is checked in clean_target_ref
    link_type = forms.ChoiceField(choices=RecordLink.LINK_TYPES)
    target_ref = forms.CharField(label="Record reference", max_length=20,
                                 help_text="e.g. CR-0003")

    def __init__(self, *args, source=None, user=None, **kwargs):
        self.source = source
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_target_ref(self):
        ref = self.cleaned_data["target_ref"].strip().upper()
        try:
            target = Record.objects.get(ref=ref)
        except Record.DoesNotExist:
            raise forms.ValidationError(f"No record {ref}.")
        if self.source and target.pk == self.source.pk:
            raise forms.ValidationError("A record cannot link to itself.")
        if self.user is not None:
            from .access import can_access
            if not can_access(self.user, target.device):
                raise forms.ValidationError(f"No record {ref}.")
        self.cleaned_data["target"] = target
        return ref


def validate_upload(f):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in settings.QMS_ATTACHMENT_EXTENSIONS:
        raise forms.ValidationError(
            f"File type {ext or '(none)'} is not allowed. Allowed: "
            + ", ".join(settings.QMS_ATTACHMENT_EXTENSIONS))
    if f.size > settings.QMS_ATTACHMENT_MAX_MB * 1024 * 1024:
        raise forms.ValidationError(f"Files must be under {settings.QMS_ATTACHMENT_MAX_MB} MB.")
    return f


class AttachmentForm(forms.ModelForm):
    confirm_no_participant_data = forms.BooleanField(
        label="This file contains no patient or participant data (names, NHS or hospital "
              "numbers, identifiable images or recordings).")

    class Meta:
        model = Attachment
        fields = ["file", "description"]

    def clean_file(self):
        return validate_upload(self.cleaned_data["file"])


# --- documents -----------------------------------------------------------------

class DocumentForm(DeviceScopedForm, forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "doc_type", "device", "tech_file_section", "description", "owner",
                  "review_period_months"]
        widgets = _widgets(fields)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["doc_type"].disabled = True


class VersionForm(DeviceScopedForm, forms.ModelForm):
    class Meta:
        model = DocumentVersion
        fields = ["version", "change_summary", "file", "change_request"]
        widgets = _widgets(fields)

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f and hasattr(f, "size") and not getattr(f, "_committed", True):
            validate_upload(f)
        return f


class TrainingRequirementForm(forms.Form):
    group = forms.ModelChoiceField(queryset=Group.objects.filter(name__in=wf.ANY_ROLE),
                                   label="Role that must be trained")


# --- risk --------------------------------------------------------------------------

class HazardForm(DeviceScopedForm, forms.ModelForm):
    class Meta:
        model = Hazard
        fields = ["device", "title", "hazard", "cause", "hazardous_situation", "harm", "software_item",
                  "owner", "severity_initial", "probability_initial", "severity_residual",
                  "probability_residual", "benefit_risk_rationale"]
        widgets = _widgets(fields)


class RiskControlForm(DeviceScopedForm, forms.ModelForm):
    class Meta:
        model = RiskControl
        fields = ["description", "control_type", "implemented_by", "verification_evidence",
                  "verified"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, hazard=None, **kwargs):
        super().__init__(*args, **kwargs)
        if hazard is not None:
            self.fields["implemented_by"].queryset = self.fields["implemented_by"].queryset \
                .filter(device=hazard.device)

    def clean(self):
        data = super().clean()
        if data.get("verified") and not data.get("verification_evidence"):
            self.add_error("verification_evidence", "Evidence is required to mark it verified.")
        return data


# --- suppliers -----------------------------------------------------------------------

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "category", "criticality", "scope", "contact",
                  "evaluation_interval_months", "notes"]
        widgets = _widgets(fields)


class SupplierEvaluationForm(forms.Form):
    outcome = forms.ChoiceField(choices=[c for c in Supplier.STATUSES if c[0] != "proposed"])
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}),
                            help_text="Evidence reviewed and conclusion.")
    password = forms.CharField(label="Password or signing PIN", widget=forms.PasswordInput)


class SoupItemForm(DeviceScopedForm, forms.ModelForm):
    class Meta:
        model = SoupItem
        fields = ["name", "version", "supplier", "devices", "software_item", "purpose", "licence",
                  "safety_class", "known_anomalies", "last_anomaly_review", "active"]
        widgets = _widgets(fields)


# --- devices -----------------------------------------------------------------------------

ROLE_CHOICES = [(r, r) for r in wf.ROLES]


class RolesField(forms.MultipleChoiceField):
    """Tick-boxes for the roles a person holds on one device."""
    widget = forms.CheckboxSelectMultiple

    def __init__(self, **kwargs):
        kwargs.setdefault("choices", ROLE_CHOICES)
        kwargs.setdefault("label", "Roles on this device")
        super().__init__(**kwargs)


class TeamMemberForm(forms.Form):
    user = forms.ModelChoiceField(queryset=None, label="Person")
    roles = RolesField()
    note = forms.CharField(max_length=200, required=False, label="Responsibility (optional)")

    def __init__(self, *args, device=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model
        current = device.memberships.filter(active=True).values("user") if device else []
        self.fields["user"].queryset = get_user_model().objects.filter(
            is_active=True).exclude(pk__in=current).order_by("username")


class TeamRolesForm(forms.Form):
    roles = RolesField(required=False,
                       help_text="Untick every role to keep someone on the team with no role.")
    note = forms.CharField(max_length=200, required=False, label="Responsibility (optional)")


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ["name", "code", "owner", "current_version", "regulatory_status", "markets",
                  "description", "intended_purpose", "intended_users", "patient_population",
                  "contraindications", "classification", "classification_rule",
                  "software_safety_class", "software_items", "basic_udi_di", "manufacturer",
                  "uk_responsible_person", "approved_body", "standards_applied", "active"]
        widgets = _widgets(fields)


# --- account ---------------------------------------------------------------------------

class SigningPinForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput, required=False)
    pin = forms.CharField(label="New signing PIN", widget=forms.PasswordInput, min_length=6,
                          help_text="At least 6 characters. Used only to sign records.")
    pin_confirm = forms.CharField(label="Repeat signing PIN", widget=forms.PasswordInput)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if not (user and user.has_usable_password()):
            del self.fields["current_password"]

    def clean(self):
        data = super().clean()
        if data.get("pin") != data.get("pin_confirm"):
            self.add_error("pin_confirm", "The PINs do not match.")
        if "current_password" in self.fields and not self.user.check_password(
                data.get("current_password") or ""):
            self.add_error("current_password", "Password not recognised.")
        return data


# --- invitations ---------------------------------------------------------------------------

class InvitationForm(forms.Form):
    """Email, roles on each device the inviter manages, expiry and an optional message."""
    email = forms.EmailField(label="Email address")
    expires_in_days = forms.IntegerField(label="Link expires after (days)", min_value=1)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False,
                              label="Message (optional)")

    def __init__(self, *args, devices=(), first=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expires_in_days"].initial = settings.QMS_INVITATION_DAYS
        self.fields["expires_in_days"].validators.append(
            MaxValueValidator(settings.QMS_INVITATION_MAX_DAYS))
        self.fields["expires_in_days"].widget.attrs["max"] = settings.QMS_INVITATION_MAX_DAYS
        self.devices = sorted(devices, key=lambda d: (d != first, d.name))
        for d in self.devices:
            self.fields[f"roles_{d.pk}"] = RolesField(
                required=False, label=f"Roles on {d.name} ({d.code})")
        order = ["email"] + [f"roles_{d.pk}" for d in self.devices] + ["expires_in_days",
                                                                        "message"]
        self.order_fields(order)

    @staticmethod
    def help_field_name(name):
        return "roles" if name.startswith("roles_") else name

    def grants(self) -> dict:
        return {d: self.cleaned_data.get(f"roles_{d.pk}") or [] for d in self.devices}

    def clean(self):
        data = super().clean()
        if self.devices and not any(data.get(f"roles_{d.pk}") for d in self.devices):
            raise forms.ValidationError("Tick at least one role on at least one device.")
        return data


# --- account requests -------------------------------------------------------------

ACCESS_ROLE_CHOICES = [("", "Choose…")] + [(r, r) for r in wf.ANY_ROLE] + [
    ("Auditor (read only)", "Auditor (read only)"), ("Not sure", "Not sure")]


class AccessRequestForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(label="Work email address")
    organisation = forms.CharField(max_length=200)
    position = forms.CharField(max_length=200, label="Job title or position")
    devices = forms.CharField(max_length=300, label="Devices or projects")
    role = forms.ChoiceField(choices=ACCESS_ROLE_CHOICES, label="Role you need")
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}),
                             label="What you'll use SAMD_QMS for", max_length=2000)
    agree = forms.BooleanField(label="These details are correct, and I understand that QA will "
                                     "review them and may contact me.")

    def __init__(self, *args, known_email="", **kwargs):
        super().__init__(*args, **kwargs)
        if known_email:  # verified by the sign-in provider: shown, not asked for
            del self.fields["email"]


class AccessApproveForm(forms.Form):
    device = forms.ModelChoiceField(queryset=None, label="Device team")
    roles = RolesField()
    note = forms.CharField(max_length=500, required=False, label="Note (optional)")

    def __init__(self, *args, devices=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Device
        self.fields["device"].queryset = Device.objects.filter(
            pk__in=[d.pk for d in (devices or [])]).order_by("name")


class AccessDeclineForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=2000,
                             label="Reason (sent to the person)")
