import csv
from django.contrib import admin
from django.http import HttpResponse
from .models import Lead, LeadSearch
from .services.exports import HEADERS, lead_row


@admin.action(description="Export Selected Leads to CSV")
def export_leads_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="leads_export.csv"'
    writer = csv.writer(response)
    writer.writerow(HEADERS)
    for lead in queryset:
        writer.writerow(lead_row(lead))
    return response


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        "company_name", "domain", "primary_email", "phone",
        "has_android_app", "has_chatbot", "server_response_time_ms",
        "audit_status", "lead_score", "status", "created_at"
    ]
    list_filter = ["audit_status", "android_status", "chatbot_status", "status", "has_android_app", "has_chatbot", "niche", "created_at"]
    search_fields = ["company_name", "domain", "primary_email", "phone", "niche", "location"]
    list_editable = ["status"]
    actions = [export_leads_csv]
    readonly_fields = ["created_at", "updated_at", "lead_score", "last_audited_at", "audit_report"]


@admin.register(LeadSearch)
class LeadSearchAdmin(admin.ModelAdmin):
    list_display = ["query", "location", "total_found", "created_at"]
    search_fields = ["query", "location"]
    readonly_fields = ["created_at"]
