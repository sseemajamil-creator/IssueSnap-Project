"""
IssueSnap Notification Models
"""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

NOTIFICATION_TYPES = [
    ('complaint_submitted', 'Complaint Submitted'),
    ('status_changed', 'Status Changed'),
    ('complaint_assigned', 'Complaint Assigned'),
    ('ai_analyzed', 'AI Analysis Complete'),
    ('duplicate_found', 'Duplicate Detected'),
    ('admin_note', 'Admin Note'),
    ('general', 'General'),
]


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, default='general')
    complaint = models.ForeignKey(
        'complaints.Complaint', on_delete=models.CASCADE,
        null=True, blank=True, related_name='notifications'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f'{self.title} -> {self.user.email}'

    def get_icon(self):
        icons = {
            'complaint_submitted': 'bi-check-circle',
            'status_changed': 'bi-arrow-repeat',
            'complaint_assigned': 'bi-person-check',
            'ai_analyzed': 'bi-cpu',
            'duplicate_found': 'bi-files',
            'admin_note': 'bi-chat-dots',
            'general': 'bi-bell',
        }
        return icons.get(self.notification_type, 'bi-bell')

    def get_badge_class(self):
        badges = {
            'complaint_submitted': 'bg-success',
            'status_changed': 'bg-primary',
            'complaint_assigned': 'bg-info',
            'ai_analyzed': 'bg-purple',
            'duplicate_found': 'bg-warning',
            'admin_note': 'bg-secondary',
            'general': 'bg-secondary',
        }
        return badges.get(self.notification_type, 'bg-secondary')
