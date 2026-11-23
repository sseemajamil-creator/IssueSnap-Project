from django.urls import path
from . import views

app_name = 'complaints'

urlpatterns = [
    path('dashboard/', views.citizen_dashboard, name='citizen_dashboard'),
    path('report/', views.report_issue, name='report_issue'),
    path('my-complaints/', views.my_complaints, name='my_complaints'),
    path('complaint/<str:complaint_id>/', views.complaint_detail, name='complaint_detail'),
    path('track/', views.track_complaint, name='track_complaint'),
    path('history/', views.complaint_history, name='complaint_history'),
    path('public-issues/', views.public_issues, name='public_issues'),
]
