"""
IssueSnap URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django Admin
    path('django-admin/', admin.site.urls),

    # Public pages
    path('', include('issuesnap.apps.pages.urls', namespace='pages')),

    # Accounts (auth)
    path('accounts/', include('issuesnap.apps.accounts.urls', namespace='accounts')),

    # Complaints (citizen + admin)
    path('citizen/', include('issuesnap.apps.complaints.urls', namespace='complaints')),

    # Admin panel
    path('admin-panel/', include('issuesnap.apps.complaints.admin_urls', namespace='admin_complaints')),

    # AI Engine API
    path('api/ai/', include('issuesnap.apps.ai_engine.urls', namespace='ai_engine')),

    # Notifications
    path('notifications/', include('issuesnap.apps.notifications.urls', namespace='notifications')),

    # Research
    path('research/', include('issuesnap.apps.research.urls', namespace='research')),
]

# Serve media during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler404 = 'issuesnap.apps.pages.views.error_404'
handler500 = 'issuesnap.apps.pages.views.error_500'
