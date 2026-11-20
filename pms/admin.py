from django.contrib import admin

from .models import ExternalIssue, PmsProfile, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("number", "kind", "device", "status", "created_at")
    list_filter = ("kind", "status")
    readonly_fields = ("number", "reporter_type", "created_at")


@admin.register(PmsProfile)
class PmsProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "user_type", "organisation")


@admin.register(ExternalIssue)
class ExternalIssueAdmin(admin.ModelAdmin):
    list_display = ("report", "provider", "reference")
