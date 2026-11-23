from django.contrib import admin
from .models import ModelVersion, AIClassification, NLPAnalysis


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = ['name', 'version', 'model_type', 'is_active', 'is_trained', 'accuracy', 'f1_score']
    list_filter = ['model_type', 'is_active', 'is_trained']


@admin.register(AIClassification)
class AIClassificationAdmin(admin.ModelAdmin):
    list_display = ['complaint', 'predicted_class', 'confidence_score', 'is_above_threshold', 'created_at']
    list_filter = ['is_above_threshold', 'predicted_class']
    search_fields = ['complaint__complaint_id']


@admin.register(NLPAnalysis)
class NLPAnalysisAdmin(admin.ModelAdmin):
    list_display = ['complaint', 'is_urgent', 'suggested_category', 'created_at']
    list_filter = ['is_urgent']
