from django.urls import path
from . import admin_views

app_name = 'admin_complaints'

urlpatterns = [
    path('dashboard/', admin_views.admin_dashboard, name='dashboard'),
    path('complaints/', admin_views.manage_complaints, name='manage_complaints'),
    path('complaints/<str:complaint_id>/', admin_views.admin_complaint_detail, name='complaint_detail'),
    path('complaints/<str:complaint_id>/assign/', admin_views.assign_complaint, name='assign_complaint'),
    path('users/', admin_views.manage_users, name='manage_users'),
    path('categories/', admin_views.manage_categories, name='manage_categories'),
    path('duplicates/', admin_views.review_duplicates, name='review_duplicates'),
    path('duplicates/<int:match_id>/resolve/', admin_views.resolve_duplicate, name='resolve_duplicate'),
    path('ai-results/', admin_views.review_ai_results, name='review_ai_results'),
    path('analytics/', admin_views.analytics_reports, name='analytics_reports'),
    path('export/csv/', admin_views.export_complaints_csv, name='export_csv'),
]
