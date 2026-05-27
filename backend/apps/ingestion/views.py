import hashlib
from datetime import datetime, timezone

from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from apps.core.models import Tenant
from apps.review.models import EmissionRecord
from .models import DataSource, IngestionRun, RawRecord
from .serializers import DataSourceSerializer, IngestionRunSerializer, RawRecordSerializer
from .parsers import sap, utility, travel


# Maps each source type to its parser function
PARSERS = {
    'SAP_FUEL':             sap.parse_sap_file,
    'UTILITY_ELECTRICITY':  utility.parse_utility_file,
    'TRAVEL':               travel.parse_travel_file,
}


class DataSourceListCreateView(generics.ListCreateAPIView):
    serializer_class = DataSourceSerializer

    def get_queryset(self):
        return DataSource.objects.filter(tenant__isnull=False).select_related('tenant')

    def perform_create(self, serializer):
        tenant = Tenant.objects.first()
        serializer.save(tenant=tenant)


class IngestionRunListView(generics.ListAPIView):
    serializer_class = IngestionRunSerializer

    def get_queryset(self):
        qs = IngestionRun.objects.select_related('data_source').order_by('-started_at')
        source_id = self.request.query_params.get('source')
        if source_id:
            qs = qs.filter(data_source_id=source_id)
        return qs


class IngestionRunDetailView(generics.RetrieveAPIView):
    serializer_class = IngestionRunSerializer
    queryset = IngestionRun.objects.select_related('data_source')


class RawRecordListView(generics.ListAPIView):
    serializer_class = RawRecordSerializer

    def get_queryset(self):
        run_id = self.kwargs['run_id']
        return RawRecord.objects.filter(ingestion_run_id=run_id)


class IngestFileView(APIView):

    def post(self, request):
        source_id = request.data.get('source_id')
        if not source_id:
            return Response({'error': 'source_id is required'}, status=400)

        source = get_object_or_404(DataSource, pk=source_id)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'No file uploaded'}, status=400)

        file_bytes = uploaded.read()
        file_hash  = hashlib.sha256(file_bytes).hexdigest()

        # Block duplicate uploads - same file hash means same content
        if IngestionRun.objects.filter(file_hash=file_hash, status='COMPLETED').exists():
            return Response({'error': 'This file has already been ingested successfully'}, status=409)

        run = IngestionRun.objects.create(
            data_source=source,
            triggered_by=request.user,
            status='PROCESSING',
            file_name=uploaded.name,
            file_hash=file_hash,
        )

        parser = PARSERS.get(source.source_type)
        if not parser:
            run.status = 'FAILED'
            run.error_summary = ['No parser for source type: ' + source.source_type]
            run.completed_at = datetime.now(timezone.utc)
            run.save()
            return Response({'error': 'Unsupported source type: ' + source.source_type}, status=400)

        try:
            rows, file_errors = parser(file_bytes)
        except Exception as e:
            run.status = 'FAILED'
            run.error_summary = [str(e)]
            run.completed_at = datetime.now(timezone.utc)
            run.save()
            return Response({'error': 'Parse error: ' + str(e)}, status=500)

        if file_errors:
            run.status = 'FAILED'
            run.error_summary = file_errors
            run.completed_at = datetime.now(timezone.utc)
            run.save()
            return Response({'error': file_errors[0]}, status=400)

        run.records_total = len(rows)
        ok_count  = 0
        bad_count = 0
        errors_list = []

        for i, row in enumerate(rows, start=1):
            success    = row.get('ok', False)
            raw_data   = row.get('raw_data', {})
            row_errors = row.get('errors', [])
            suspicious = row.get('suspicious', False)
            warnings   = row.get('warnings', [])

            if not success:
                RawRecord.objects.create(
                    ingestion_run=run,
                    row_index=i,
                    raw_data=raw_data,
                    parse_status='FAILED',
                    parse_errors=row_errors,
                )
                bad_count += 1
                if row_errors:
                    errors_list.append({'row': i, 'errors': row_errors})
                continue

            status_label = 'SUSPICIOUS' if suspicious else 'OK'
            raw = RawRecord.objects.create(
                ingestion_run=run,
                row_index=i,
                raw_data=raw_data,
                parse_status=status_label,
                parse_errors=warnings,
            )

            d = row['data']
            review_status = 'FLAGGED' if suspicious else 'PENDING'

            EmissionRecord.objects.create(
                tenant=source.tenant,
                raw_record=raw,
                scope=d['scope'],
                ghg_category=d['ghg_category'],
                source_type=d['source_type'],
                source_id=d['source_id'],
                activity_type=d['activity_type'],
                quantity=d['quantity'],
                unit=d['unit'],
                quantity_original=d['quantity_original'],
                unit_original=d['unit_original'],
                conversion_factor=d['conversion_factor'],
                period_start=d['period_start'],
                period_end=d['period_end'],
                facility_code=d['facility_code'],
                facility_name=d['facility_name'],
                country_code=d['country_code'],
                extra_data=d['extra_data'],
                review_status=review_status,
            )
            ok_count += 1

        run.records_parsed = ok_count
        run.records_failed = bad_count
        run.error_summary  = errors_list[:20]  # store at most 20 errors to keep the field small
        run.status         = 'COMPLETED'
        run.completed_at   = datetime.now(timezone.utc)
        run.save()

        return Response(IngestionRunSerializer(run).data, status=201)
