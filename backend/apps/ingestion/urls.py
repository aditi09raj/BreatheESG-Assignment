from django.urls import path
from .views import (
    DataSourceListCreateView,
    IngestionRunListView,
    IngestionRunDetailView,
    RawRecordListView,
    IngestFileView,
)

urlpatterns = [
    path('sources/', DataSourceListCreateView.as_view(), name='source-list'),
    path('ingest/', IngestFileView.as_view(), name='ingest-file'),
    path('runs/', IngestionRunListView.as_view(), name='run-list'),
    path('runs/<int:pk>/', IngestionRunDetailView.as_view(), name='run-detail'),
    path('runs/<int:run_id>/records/', RawRecordListView.as_view(), name='raw-record-list'),
]
