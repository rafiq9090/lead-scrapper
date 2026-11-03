from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('lead/<int:lead_id>/', views.lead_detail, name='detail'),
    path('lead/<int:lead_id>/reaudit/', views.reaudit_lead, name='reaudit'),
    path('api/prospect/', views.api_start_prospecting, name='api_prospect'),
    path('api/task/<str:task_id>/', views.api_task_status, name='api_task_status'),
    path('api/audit/', views.api_audit_single_domain, name='api_audit'),
    path('api/lead/<int:lead_id>/status/', views.api_update_lead_status, name='api_update_status'),
    path('export/csv/', views.export_leads_csv, name='export_csv'),
    path('export/excel/', views.export_leads_excel, name='export_excel'),
]
