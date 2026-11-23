"""
IssueSnap AI Engine Models
"""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ModelVersion(models.Model):
    MODEL_TYPES = [
        ('cnn', 'Custom CNN'),
        ('mobilenetv2', 'MobileNetV2'),
        ('efficientnet', 'EfficientNetB0'),
        ('yolo', 'YOLOv8'),
        ('ensemble', 'Ensemble'),
        ('random_forest', 'Random Forest (scikit-learn)'),
    ]

    name = models.CharField(max_length=100)
    version = models.CharField(max_length=20)
    model_type = models.CharField(max_length=30, choices=MODEL_TYPES)
    description = models.TextField(blank=True)
    model_file = models.CharField(max_length=255)
    input_size = models.IntegerField(default=224)
    num_classes = models.IntegerField(default=7)
    class_names = models.JSONField(default=list)
    is_active = models.BooleanField(default=False)
    is_trained = models.BooleanField(default=False)

    # Performance metrics
    accuracy = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    inference_time_ms = models.FloatField(null=True, blank=True)

    # Training info
    training_dataset = models.CharField(max_length=200, blank=True)
    training_samples = models.IntegerField(null=True, blank=True)
    validation_samples = models.IntegerField(null=True, blank=True)
    test_samples = models.IntegerField(null=True, blank=True)
    epochs_trained = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'model_versions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} v{self.version} ({self.model_type})'


class AIClassification(models.Model):
    complaint = models.ForeignKey(
        'complaints.Complaint', on_delete=models.CASCADE, related_name='ai_classifications'
    )
    complaint_image = models.ForeignKey(
        'complaints.ComplaintImage', on_delete=models.CASCADE, null=True, blank=True
    )
    model_version = models.ForeignKey(ModelVersion, on_delete=models.SET_NULL, null=True)

    predicted_class = models.CharField(max_length=100)
    confidence_score = models.FloatField()
    top_predictions = models.JSONField(default=list)
    all_class_probabilities = models.JSONField(default=dict)

    # Bounding boxes (for object detection models)
    bounding_boxes = models.JSONField(default=list, blank=True)
    annotated_image = models.ImageField(upload_to='ai_results/', null=True, blank=True)

    # Processing info
    preprocessing_time_ms = models.FloatField(null=True, blank=True)
    inference_time_ms = models.FloatField(null=True, blank=True)
    is_above_threshold = models.BooleanField(default=False)
    threshold_used = models.FloatField(default=0.60)

    # Admin review
    admin_verified = models.BooleanField(null=True, blank=True)
    admin_corrected_class = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_classifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'AI: {self.complaint.complaint_id} -> {self.predicted_class} ({self.confidence_score:.2f})'


class NLPAnalysis(models.Model):
    complaint = models.OneToOneField(
        'complaints.Complaint', on_delete=models.CASCADE, related_name='nlp_analysis'
    )

    # Cleaned text
    cleaned_text = models.TextField(blank=True)

    # Keywords
    extracted_keywords = models.JSONField(default=list)
    urgency_keywords = models.JSONField(default=list)
    is_urgent = models.BooleanField(default=False)

    # TF-IDF
    tfidf_vector = models.BinaryField(null=True, blank=True)

    # Category suggestion
    suggested_category = models.CharField(max_length=100, blank=True)
    category_confidence = models.FloatField(null=True, blank=True)

    # Summary (if available)
    auto_summary = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'nlp_analyses'

    def __str__(self):
        return f'NLP: {self.complaint.complaint_id}'
