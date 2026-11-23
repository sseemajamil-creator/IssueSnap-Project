"""
IssueSnap Complaints Models
"""
import os
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


DISTRICT_CHOICES = [
    ('karachi', 'Karachi'),
    ('lahore', 'Lahore'),
    ('islamabad', 'Islamabad'),
    ('rawalpindi', 'Rawalpindi'),
    ('faisalabad', 'Faisalabad'),
    ('multan', 'Multan'),
    ('peshawar', 'Peshawar'),
    ('quetta', 'Quetta'),
    ('sialkot', 'Sialkot'),
    ('gujranwala', 'Gujranwala'),
    ('other', 'Other'),
]


class ComplaintCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='bi-exclamation-triangle')
    color = models.CharField(max_length=20, default='#2563EB')
    is_ai_supported = models.BooleanField(default=False)
    ai_class_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'complaint_categories'
        ordering = ['order', 'name']
        verbose_name = 'Complaint Category'
        verbose_name_plural = 'Complaint Categories'

    def __str__(self):
        return self.name


def complaint_image_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'complaints/{instance.complaint.complaint_id}/{filename}'


class Complaint(models.Model):
    # Status choices
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    PROCESSING = 'processing'
    RESOLVED = 'resolved'
    COMPLETED = 'completed'
    REJECTED = 'rejected'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (IN_PROGRESS, 'In Progress'),
        (PROCESSING, 'Processing'),
        (RESOLVED, 'Resolved'),
        (COMPLETED, 'Completed'),
        (REJECTED, 'Rejected'),
    ]

    # Priority choices
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'

    PRIORITY_CHOICES = [
        (CRITICAL, 'Critical'),
        (HIGH, 'High'),
        (MEDIUM, 'Medium'),
        (LOW, 'Low'),
    ]

    # Core fields
    complaint_id = models.CharField(max_length=20, unique=True, editable=False)
    citizen = models.ForeignKey(User, on_delete=models.CASCADE, related_name='complaints')
    category = models.ForeignKey(ComplaintCategory, on_delete=models.SET_NULL, null=True, related_name='complaints')

    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=MEDIUM)

    # Location
    district = models.CharField(max_length=100, choices=DISTRICT_CHOICES)
    area = models.CharField(max_length=200)
    address = models.TextField()
    landmark = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # Admin fields
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_complaints', limit_choices_to={'role': 'admin'}
    )
    admin_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    # AI
    ai_analyzed = models.BooleanField(default=False)
    ai_confirmed = models.BooleanField(default=False)

    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Tracking
    view_count = models.IntegerField(default=0)
    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='duplicate_reports'
    )

    class Meta:
        db_table = 'complaints'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['district']),
            models.Index(fields=['citizen']),
            models.Index(fields=['submitted_at']),
        ]

    def __str__(self):
        return f'{self.complaint_id} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.complaint_id:
            self.complaint_id = self._generate_complaint_id()
        if self.status in [self.RESOLVED, self.COMPLETED] and not self.resolved_at:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_complaint_id(cls):
        year = timezone.now().year
        prefix = f'ISS-{year}-'
        last = cls.objects.filter(complaint_id__startswith=prefix).order_by('-complaint_id').first()
        if last:
            try:
                seq = int(last.complaint_id.split('-')[2]) + 1
            except (IndexError, ValueError):
                seq = 1
        else:
            seq = 1
        return f'{prefix}{seq:06d}'

    def get_status_badge_class(self):
        mapping = {
            self.PENDING: 'badge-warning',
            self.IN_PROGRESS: 'badge-info',
            self.PROCESSING: 'badge-primary',
            self.RESOLVED: 'badge-success',
            self.COMPLETED: 'badge-success',
            self.REJECTED: 'badge-danger',
        }
        return mapping.get(self.status, 'badge-secondary')

    def get_priority_badge_class(self):
        mapping = {
            self.CRITICAL: 'badge-danger',
            self.HIGH: 'badge-warning',
            self.MEDIUM: 'badge-info',
            self.LOW: 'badge-secondary',
        }
        return mapping.get(self.priority, 'badge-secondary')

    def get_primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()


class ComplaintImage(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='complaints/')
    is_primary = models.BooleanField(default=False)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.IntegerField(default=0)

    class Meta:
        db_table = 'complaint_images'
        ordering = ['-is_primary', 'uploaded_at']

    def __str__(self):
        return f'Image for {self.complaint.complaint_id}'


class ComplaintStatusHistory(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    note = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'complaint_status_history'
        ordering = ['changed_at']

    def __str__(self):
        return f'{self.complaint.complaint_id}: {self.old_status} -> {self.new_status}'


class DuplicateComplaintMatch(models.Model):
    original_complaint = models.ForeignKey(
        Complaint, on_delete=models.CASCADE, related_name='duplicate_matches_as_original'
    )
    duplicate_complaint = models.ForeignKey(
        Complaint, on_delete=models.CASCADE, related_name='duplicate_matches_as_duplicate'
    )
    similarity_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    text_similarity = models.FloatField(default=0.0)
    geographic_distance_km = models.FloatField(null=True, blank=True)
    category_match = models.BooleanField(default=False)
    is_confirmed_duplicate = models.BooleanField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    detection_method = models.CharField(max_length=100, default='tfidf_cosine')

    class Meta:
        db_table = 'duplicate_complaint_matches'
        unique_together = [['original_complaint', 'duplicate_complaint']]

    def __str__(self):
        return f'Duplicate: {self.duplicate_complaint.complaint_id} ~ {self.original_complaint.complaint_id} ({self.similarity_score:.2f})'


class PriorityPrediction(models.Model):
    complaint = models.OneToOneField(Complaint, on_delete=models.CASCADE, related_name='priority_prediction')
    predicted_priority = models.CharField(max_length=20)
    confidence_score = models.FloatField(null=True, blank=True)
    method = models.CharField(max_length=50, default='rule_based')
    reasoning = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'priority_predictions'

    def __str__(self):
        return f'Priority for {self.complaint.complaint_id}: {self.predicted_priority}'


class AdministratorAssignment(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='assignments')
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='complaint_assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='complaint_assignements_given')
    note = models.TextField(blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'administrator_assignments'

    def __str__(self):
        return f'{self.complaint.complaint_id} assigned to {self.assigned_to.get_full_name()}'
