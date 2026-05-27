from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Tenant


class DataSource(models.Model):
    SOURCE_TYPES = [
        ('SAP_FUEL', 'SAP Fuel & Procurement'),
        ('UTILITY_ELECTRICITY', 'Utility Electricity'),
        ('TRAVEL', 'Corporate Travel (Concur/Navan)'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='sources')
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.tenant.name} — {self.name}'


class IngestionRun(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='runs')
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    file_name = models.CharField(max_length=500)
    # SHA-256 of the uploaded file — used to detect duplicate uploads
    file_hash = models.CharField(max_length=64, blank=True)
    records_total = models.IntegerField(default=0)
    records_parsed = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    error_summary = models.JSONField(default=list)

    def __str__(self):
        return f'{self.data_source.name} @ {self.started_at:%Y-%m-%d %H:%M}'


class RawRecord(models.Model):
    PARSE_STATUS = [
        ('OK', 'Parsed OK'),
        ('FAILED', 'Parse Failed'),
        ('SUSPICIOUS', 'Suspicious — needs review'),
    ]
    ingestion_run = models.ForeignKey(IngestionRun, on_delete=models.CASCADE, related_name='raw_records')
    row_index = models.IntegerField()
    # Original key-value pairs from the source file, preserved verbatim
    raw_data = models.JSONField()
    parse_status = models.CharField(max_length=20, choices=PARSE_STATUS, default='OK')
    parse_errors = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['row_index']

    def __str__(self):
        return f'Row {self.row_index} of {self.ingestion_run}'
