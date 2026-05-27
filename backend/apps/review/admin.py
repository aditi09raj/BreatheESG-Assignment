from django.contrib import admin
from .models import EmissionRecord, EmissionRecordEdit


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'scope', 'source_type', 'activity_type', 'quantity', 'unit', 'period_start', 'review_status', 'locked_for_audit']
    list_filter = ['review_status', 'scope', 'source_type', 'locked_for_audit']
    readonly_fields = ['created_at', 'updated_at', 'version', 'locked_at', 'reviewed_at']
    search_fields = ['activity_type', 'facility_name', 'source_id']


@admin.register(EmissionRecordEdit)
class EmissionRecordEditAdmin(admin.ModelAdmin):
    list_display = ['emission_record', 'edited_by', 'edited_at', 'field_name', 'old_value', 'new_value']
    readonly_fields = ['edited_at']
