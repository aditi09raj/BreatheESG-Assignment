from datetime import datetime, timezone

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count
from django.shortcuts import get_object_or_404

from apps.core.models import Tenant
from .models import EmissionRecord, EmissionRecordEdit
from .serializers import EmissionRecordSerializer, EmissionRecordUpdateSerializer


class EmissionRecordListView(generics.ListAPIView):
    serializer_class = EmissionRecordSerializer

    def get_queryset(self):
        all_records = EmissionRecord.objects.select_related('raw_record', 'reviewed_by').prefetch_related('edits')

        filter_status = self.request.query_params.get('status')
        if filter_status:
            all_records = all_records.filter(review_status=filter_status)

        filter_scope = self.request.query_params.get('scope')
        if filter_scope:
            all_records = all_records.filter(scope=filter_scope)

        filter_source_type = self.request.query_params.get('source_type')
        if filter_source_type:
            all_records = all_records.filter(source_type=filter_source_type)

        filter_run_id = self.request.query_params.get('run')
        if filter_run_id:
            all_records = all_records.filter(raw_record__ingestion_run_id=filter_run_id)

        return all_records.order_by('-created_at')


class EmissionRecordDetailView(generics.RetrieveAPIView):
    serializer_class = EmissionRecordSerializer
    queryset = EmissionRecord.objects.select_related('raw_record', 'reviewed_by').prefetch_related('edits')


class EmissionRecordUpdateView(generics.UpdateAPIView):
    serializer_class = EmissionRecordUpdateSerializer
    queryset = EmissionRecord.objects.all()
    http_method_names = ['patch']

    def get_serializer_context(self):
        context_data = super().get_serializer_context()
        context_data['request'] = self.request
        return context_data

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        record = self.get_object()
        serializer = self.get_serializer(record, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        saved_record = serializer.save()
        # Return the full record (with version, edits, etc.) not the update-subset serializer
        return Response(
            EmissionRecordSerializer(
                saved_record,
                context=self.get_serializer_context()
            ).data
        )


class ReviewActionView(APIView):
    """POST to /records/{id}/review/ with action=approve|reject|flag."""

    def post(self, request, pk):
        record = get_object_or_404(EmissionRecord, pk=pk)

        if record.locked_for_audit:
            return Response({'error': 'Record is locked for audit'}, status=400)

        action = request.data.get('action')
        notes = request.data.get('notes', '')

        valid_actions = {
            'approve': 'APPROVED',
            'reject':  'REJECTED',
            'flag':    'FLAGGED',
            'reset':   'PENDING',
        }

        if action not in valid_actions:
            return Response({'error': f'Unknown action {action!r}. Use: approve, reject, flag, reset'}, status=400)

        old_status = record.review_status
        new_status = valid_actions[action]

        record.review_status = new_status
        record.reviewed_by = request.user
        record.reviewed_at = datetime.now(timezone.utc)
        record.review_notes = notes

        if action == 'approve':
            record.locked_for_audit = True
            record.locked_at = datetime.now(timezone.utc)

        EmissionRecordEdit.objects.create(
            emission_record=record,
            edited_by=request.user,
            record_version=record.version,
            field_name='review_status',
            old_value=old_status,
            new_value=new_status,
            reason=notes or f'{action} via review dashboard',
        )

        record.version += 1
        record.save()

        return Response(EmissionRecordSerializer(record).data)


class BulkReviewView(APIView):
    """POST to /records/bulk-action/ with ids=[...] and action=approve|reject|flag."""

    def post(self, request):
        record_ids = request.data.get('ids', [])
        action = request.data.get('action')
        notes = request.data.get('notes', '')

        valid_actions = {
            'approve': 'APPROVED',
            'reject':  'REJECTED',
            'flag':    'FLAGGED',
        }

        if action not in valid_actions:
            return Response({'error': f'Unknown action {action!r}'}, status=400)

        # Only process records that are not already locked
        unlocked_records = EmissionRecord.objects.filter(pk__in=record_ids, locked_for_audit=False)
        right_now = datetime.now(timezone.utc)
        new_status = valid_actions[action]

        audit_entries = []
        for record in unlocked_records:
            old_status = record.review_status
            record.review_status = new_status
            record.reviewed_by = request.user
            record.reviewed_at = right_now
            record.review_notes = notes
            if action == 'approve':
                record.locked_for_audit = True
                record.locked_at = right_now
            record.version += 1
            audit_entries.append(EmissionRecordEdit(
                emission_record=record,
                edited_by=request.user,
                record_version=record.version,
                field_name='review_status',
                old_value=old_status,
                new_value=new_status,
                reason=notes or f'bulk {action}',
            ))

        EmissionRecord.objects.bulk_update(
            unlocked_records,
            ['review_status', 'reviewed_by', 'reviewed_at', 'review_notes',
             'locked_for_audit', 'locked_at', 'version'],
        )
        EmissionRecordEdit.objects.bulk_create(audit_entries)

        return Response({'updated': len(unlocked_records)})


class DashboardStatsView(APIView):
    def get(self, request):
        all_records = EmissionRecord.objects.all()
        total_count = all_records.count()

        # Count records by review status
        by_status = {}
        for row in all_records.values('review_status').annotate(count=Count('id')):
            by_status[row['review_status']] = row['count']

        # Count records by scope number
        by_scope = {}
        for row in all_records.values('scope').annotate(count=Count('id')):
            by_scope[str(row['scope'])] = row['count']

        # Count records by data source type
        by_source = {}
        for row in all_records.values('source_type').annotate(count=Count('id')):
            by_source[row['source_type']] = row['count']

        # Grab the 5 most recently flagged records to show on the dashboard
        flagged_records = all_records.filter(review_status='FLAGGED').order_by('-created_at')[:5]

        from apps.ingestion.models import IngestionRun
        recent_runs = IngestionRun.objects.select_related('data_source').order_by('-started_at')[:5]
        from apps.ingestion.serializers import IngestionRunSerializer

        return Response({
            'total_records': total_count,
            'by_status': by_status,
            'by_scope': by_scope,
            'by_source': by_source,
            'recent_runs': IngestionRunSerializer(recent_runs, many=True).data,
            'flagged_sample': EmissionRecordSerializer(flagged_records, many=True).data,
        })
