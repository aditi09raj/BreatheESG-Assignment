from rest_framework import serializers
from .models import DataSource, IngestionRun, RawRecord


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ['id', 'tenant', 'source_type', 'name', 'description', 'created_at']
        read_only_fields = ['tenant', 'created_at']


class IngestionRunSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='data_source.name', read_only=True)
    source_type = serializers.CharField(source='data_source.source_type', read_only=True)

    class Meta:
        model = IngestionRun
        fields = [
            'id', 'data_source', 'source_name', 'source_type',
            'status', 'started_at', 'completed_at',
            'file_name', 'records_total', 'records_parsed', 'records_failed',
            'error_summary',
        ]
        read_only_fields = fields


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ['id', 'row_index', 'raw_data', 'parse_status', 'parse_errors', 'created_at']
