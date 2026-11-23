"""
IssueSnap Research Models
"""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ResearchExperiment(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    model_version = models.ForeignKey(
        'ai_engine.ModelVersion', on_delete=models.SET_NULL, null=True, blank=True
    )
    experiment_type = models.CharField(max_length=50, default='classification')

    # Dataset info
    dataset_name = models.CharField(max_length=200)
    dataset_source = models.URLField(blank=True)
    dataset_license = models.CharField(max_length=100, blank=True)
    total_samples = models.IntegerField(default=0)
    train_samples = models.IntegerField(default=0)
    val_samples = models.IntegerField(default=0)
    test_samples = models.IntegerField(default=0)
    num_classes = models.IntegerField(default=0)
    class_names = models.JSONField(default=list)

    # Hyperparameters
    hyperparameters = models.JSONField(default=dict)

    # Results
    test_accuracy = models.FloatField(null=True, blank=True)
    test_precision = models.FloatField(null=True, blank=True)
    test_recall = models.FloatField(null=True, blank=True)
    test_f1 = models.FloatField(null=True, blank=True)
    confusion_matrix = models.JSONField(default=list, blank=True)
    per_class_metrics = models.JSONField(default=dict, blank=True)
    training_history = models.JSONField(default=dict, blank=True)

    # Object detection
    mAP = models.FloatField(null=True, blank=True)
    iou_threshold = models.FloatField(null=True, blank=True)

    # Timing
    training_time_minutes = models.FloatField(null=True, blank=True)
    avg_inference_time_ms = models.FloatField(null=True, blank=True)

    notes = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'research_experiments'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.dataset_name}'


class DatasetInfo(models.Model):
    name = models.CharField(max_length=200)
    version = models.CharField(max_length=20, blank=True)
    description = models.TextField()
    source_url = models.URLField(blank=True)
    license = models.CharField(max_length=100)
    license_url = models.URLField(blank=True)
    total_images = models.IntegerField(default=0)
    num_classes = models.IntegerField(default=0)
    class_distribution = models.JSONField(default=dict)
    image_formats = models.CharField(max_length=100, blank=True)
    avg_image_size = models.CharField(max_length=50, blank=True)
    collection_year = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dataset_info'
        verbose_name = 'Dataset Information'

    def __str__(self):
        return f'{self.name} ({self.total_images} images, {self.num_classes} classes)'
