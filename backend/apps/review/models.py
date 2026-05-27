from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Tenant
from apps.ingestion.models import RawRecord


class EmissionRecord(models.Model):
    SCOPE_CHOICES = [(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')]
    REVIEW_STATUS = [
        ('PENDING',  'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('FLAGGED',  'Flagged for Investigation'),
    ]
    SOURCE_TYPES = [
        ('SAP_FUEL',             'SAP Fuel & Procurement'),
        ('UTILITY_ELECTRICITY',  'Utility Electricity'),
        ('TRAVEL',               'Corporate Travel'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='emission_records')

    # Nullable: manual entries won't have a RawRecord parent
    raw_record = models.OneToOneField(
        RawRecord, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='emission_record',
    )

    # ── Scope & GHG classification ──────────────────────────────────────────
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    # Matches GHG Protocol categories: "Stationary combustion", "Purchased electricity", "Business travel", etc.
    ghg_category = models.CharField(max_length=100)

    # ── Source provenance ────────────────────────────────────────────────────
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES)
    # Original identifier in the source system (SAP doc number, meter+date, Concur report ID)
    source_id = models.CharField(max_length=200, blank=True)

    # ── Activity data (normalised) ───────────────────────────────────────────
    activity_type = models.CharField(max_length=100)   # e.g. "diesel", "electricity_consumption", "flight"
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    unit = models.CharField(max_length=20)             # normalised unit (L, kWh, passenger-trip, room-night)
    quantity_original = models.DecimalField(max_digits=20, decimal_places=6)
    unit_original = models.CharField(max_length=20)
    # Factor applied to go from unit_original to unit (e.g. 3.78541 for GAL→L)
    conversion_factor = models.DecimalField(max_digits=20, decimal_places=10, default=1)

    # ── Time ─────────────────────────────────────────────────────────────────
    period_start = models.DateField()
    period_end = models.DateField()

    # ── Location ─────────────────────────────────────────────────────────────
    facility_code = models.CharField(max_length=50, blank=True)
    facility_name = models.CharField(max_length=200, blank=True)
    country_code = models.CharField(max_length=2, blank=True)   # ISO 3166-1 alpha-2

    # ── Source-specific fields that don't map to standard columns ────────────
    extra_data = models.JSONField(default=dict)

    # ── Review workflow ──────────────────────────────────────────────────────
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS, default='PENDING', db_index=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_records',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Once approved and locked the record is immutable — no further edits
    locked_for_audit = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    # ── Audit trail ──────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Incremented on every edit so the edit history can reference specific versions
    version = models.IntegerField(default=1)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'review_status']),
            models.Index(fields=['tenant', 'scope']),
            models.Index(fields=['source_type', 'period_start']),
        ]

    def __str__(self):
        return f'[Scope {self.scope}] {self.activity_type} {self.quantity}{self.unit} ({self.period_start})'


class EmissionRecordEdit(models.Model):
    """Append-only log of every field change made to an EmissionRecord.

    We store old/new values as text so the log survives even if the field's
    type or choices change in a future migration.
    """
    emission_record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='edits')
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    edited_at = models.DateTimeField(auto_now_add=True)
    record_version = models.IntegerField()   # snapshot of emission_record.version at time of edit
    field_name = models.CharField(max_length=100)
    old_value = models.TextField()
    new_value = models.TextField()
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ['edited_at']

    def __str__(self):
        return f'{self.emission_record_id} v{self.record_version}: {self.field_name}'
