from rest_framework import serializers
from .models import EmissionRecord, EmissionRecordEdit


class EmissionRecordEditSerializer(serializers.ModelSerializer):
    edited_by_name = serializers.CharField(source='edited_by.username', read_only=True, default='')

    class Meta:
        model = EmissionRecordEdit
        fields = ['id', 'edited_by_name', 'edited_at', 'record_version', 'field_name', 'old_value', 'new_value', 'reason']


class EmissionRecordSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    review_status_display = serializers.CharField(source='get_review_status_display', read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True, default=None)
    edits = EmissionRecordEditSerializer(many=True, read_only=True)
    ingestion_run_id = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'scope', 'scope_display', 'ghg_category',
            'source_type', 'source_type_display', 'source_id',
            'activity_type',
            'quantity', 'unit', 'quantity_original', 'unit_original', 'conversion_factor',
            'period_start', 'period_end',
            'facility_code', 'facility_name', 'country_code',
            'extra_data',
            'review_status', 'review_status_display',
            'reviewed_by_name', 'reviewed_at', 'review_notes',
            'locked_for_audit', 'locked_at',
            'created_at', 'updated_at', 'version',
            'edits',
            'ingestion_run_id',
        ]
        read_only_fields = [
            'id', 'scope_display', 'review_status_display', 'source_type_display',
            'reviewed_by_name', 'reviewed_at', 'locked_at',
            'created_at', 'updated_at', 'version', 'edits', 'ingestion_run_id',
        ]

    def get_ingestion_run_id(self, record):
        if record.raw_record:
            return record.raw_record.ingestion_run_id
        return None


class EmissionRecordUpdateSerializer(serializers.ModelSerializer):
    """Used for PATCH — only the fields an analyst is allowed to change, plus a reason."""
    reason = serializers.CharField(write_only=True, required=False, default='')

    class Meta:
        model = EmissionRecord
        fields = [
            'quantity', 'unit', 'period_start', 'period_end',
            'facility_code', 'facility_name', 'country_code',
            'review_notes', 'reason',
        ]

    def update(self, record, validated_data):
        from datetime import datetime, timezone

        if record.locked_for_audit:
            raise serializers.ValidationError('Record is locked for audit and cannot be edited.')

        edit_reason = validated_data.pop('reason', '')
        current_user = self.context['request'].user

        # These are the only fields an analyst can change
        changeable_fields = ['quantity', 'unit', 'period_start', 'period_end',
                             'facility_code', 'facility_name', 'country_code', 'review_notes']

        for field_name in changeable_fields:
            if field_name in validated_data:
                old_value = str(getattr(record, field_name))
                new_value = str(validated_data[field_name])
                if old_value != new_value:
                    EmissionRecordEdit.objects.create(
                        emission_record=record,
                        edited_by=current_user,
                        record_version=record.version,
                        field_name=field_name,
                        old_value=old_value,
                        new_value=new_value,
                        reason=edit_reason,
                    )
                    setattr(record, field_name, validated_data[field_name])

        record.version += 1
        record.save()
        return record
