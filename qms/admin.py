from django.contrib import admin

from .models import (Attachment, AuditEvent, Device, DeviceMembership, Document, DocumentVersion, Hazard, PMSSchedule,
                     Record, RecordLink, RiskControl, Signature, SoupItem, Supplier,
                     TechnicalFileBuild, TrainingAssignment, TrainingRequirement)


class ReadOnlyAdmin(admin.ModelAdmin):
    """For append-only evidence: viewable, never editable or deletable."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class NoDeleteAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


class LinkInline(admin.TabularInline):
    model = RecordLink
    fk_name = "source"
    extra = 0
    fields = ("link_type", "target", "created_by", "created_at")
    readonly_fields = ("created_by", "created_at")
    autocomplete_fields = ("target",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Record)
class RecordAdmin(NoDeleteAdmin):
    list_display = ("ref", "device", "title", "record_type", "status", "owner",
                    "patient_safety_impact", "updated_at")
    list_filter = ("device", "record_type", "status", "patient_safety_impact", "severity")
    search_fields = ("ref", "title", "description")
    readonly_fields = ("ref", "status", "created_by", "created_at", "updated_at", "closed_at")
    filter_horizontal = ("hazards",)
    inlines = [LinkInline]

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj is not None:
            ro.append("record_type")
            if obj.is_locked:
                ro = [f.name for f in self.model._meta.fields] + ["hazards"]
        return ro

    def save_formset(self, request, form, formset, change):
        for obj in formset.save(commit=False):
            if obj.pk is None:
                obj.created_by = request.user
            obj.save()


@admin.register(AuditEvent)
class AuditEventAdmin(ReadOnlyAdmin):
    list_display = ("id", "timestamp", "subject", "actor_name", "action", "comment")
    list_filter = ("action", "object_type")
    search_fields = ("record__ref", "object_ref", "actor_name", "comment")


@admin.register(Signature)
class SignatureAdmin(ReadOnlyAdmin):
    list_display = ("subject", "signer_name", "meaning", "from_status", "to_status", "signed_at")
    search_fields = ("record__ref", "object_ref", "signer_name")


@admin.register(Attachment)
class AttachmentAdmin(ReadOnlyAdmin):
    list_display = ("record", "original_name", "size", "uploaded_by", "uploaded_at")
    search_fields = ("record__ref", "original_name")


@admin.register(PMSSchedule)
class PMSScheduleAdmin(NoDeleteAdmin):
    list_display = ("name", "device", "cadence_months", "next_due", "active")
    list_filter = ("device",)
    list_editable = ("next_due", "active")


class VersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    fields = ("version", "status", "original_name", "effective_date", "next_review_date")
    readonly_fields = fields
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Document)
class DocumentAdmin(NoDeleteAdmin):
    list_display = ("number", "title", "doc_type", "device", "tech_file_section", "owner",
                    "obsolete")
    list_filter = ("doc_type", "device", "tech_file_section", "obsolete")
    search_fields = ("number", "title")
    readonly_fields = ("number", "obsolete")
    inlines = [VersionInline]


@admin.register(TrainingRequirement)
class TrainingRequirementAdmin(NoDeleteAdmin):
    list_display = ("document", "group", "active")
    list_filter = ("group", "active")


@admin.register(TrainingAssignment)
class TrainingAssignmentAdmin(ReadOnlyAdmin):
    list_display = ("user", "version", "due_date", "completed_at")
    list_filter = ("completed_at",)
    search_fields = ("user__username", "version__document__number")


class ControlInline(admin.TabularInline):
    model = RiskControl
    extra = 0
    can_delete = False


@admin.register(Hazard)
class HazardAdmin(NoDeleteAdmin):
    list_display = ("ref", "device", "title", "severity_initial", "probability_initial",
                    "severity_residual", "probability_residual", "status")
    list_filter = ("device", "status", "software_item")
    search_fields = ("ref", "title")
    readonly_fields = ("ref", "status")
    inlines = [ControlInline]


@admin.register(Supplier)
class SupplierAdmin(NoDeleteAdmin):
    list_display = ("name", "category", "criticality", "status", "last_evaluated")
    list_filter = ("status", "category", "criticality")
    readonly_fields = ("status", "last_evaluated")


class MembershipInline(admin.TabularInline):
    model = DeviceMembership
    extra = 0
    fields = ("user", "note", "active", "added_at")
    readonly_fields = ("added_at",)
    can_delete = False


@admin.register(DeviceMembership)
class DeviceMembershipAdmin(NoDeleteAdmin):
    list_display = ("user", "device", "note", "active", "added_at")
    list_filter = ("device", "active")
    search_fields = ("user__username", "user__email")


@admin.register(Device)
class DeviceAdmin(NoDeleteAdmin):
    inlines = [MembershipInline]
    list_display = ("name", "code", "classification", "software_safety_class",
                    "regulatory_status", "current_version", "active")
    list_filter = ("classification", "regulatory_status", "active")


@admin.register(TechnicalFileBuild)
class TechnicalFileBuildAdmin(ReadOnlyAdmin):
    list_display = ("label", "device", "status", "error_count", "warning_count",
                    "generated_by", "generated_at")
    list_filter = ("device", "status")


@admin.register(SoupItem)
class SoupItemAdmin(NoDeleteAdmin):
    list_display = ("name", "version", "supplier", "safety_class", "last_anomaly_review", "active")
    list_filter = ("active", "safety_class")
    search_fields = ("name",)
