from django.urls import path
from .views import (
    EmissionRecordListView,
    EmissionRecordDetailView,
    EmissionRecordUpdateView,
    ReviewActionView,
    BulkReviewView,
    DashboardStatsView,
)

urlpatterns = [
    path('records/', EmissionRecordListView.as_view(), name='record-list'),
    path('records/<int:pk>/', EmissionRecordDetailView.as_view(), name='record-detail'),
    path('records/<int:pk>/edit/', EmissionRecordUpdateView.as_view(), name='record-edit'),
    path('records/<int:pk>/review/', ReviewActionView.as_view(), name='record-review'),
    path('records/bulk/', BulkReviewView.as_view(), name='record-bulk'),
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
]
