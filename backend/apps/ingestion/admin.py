from django.contrib import admin
from .models import DataSource, IngestionRun, RawRecord


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'tenant', 'created_at']
    list_filter = ['source_type']


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = ['data_source', 'status', 'started_at', 'records_total', 'records_parsed', 'records_failed']
    list_filter = ['status', 'data_source__source_type']
    readonly_fields = ['file_hash', 'error_summary']


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display = ['ingestion_run', 'row_index', 'parse_status', 'created_at']
    list_filter = ['parse_status']
