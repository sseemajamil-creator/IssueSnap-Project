from django.contrib import admin
from .models import ResearchExperiment, DatasetInfo


@admin.register(ResearchExperiment)
class ResearchExperimentAdmin(admin.ModelAdmin):
    list_display = ['name', 'dataset_name', 'test_accuracy', 'test_f1', 'is_published', 'created_at']
    list_filter = ['is_published', 'experiment_type']


@admin.register(DatasetInfo)
class DatasetInfoAdmin(admin.ModelAdmin):
    list_display = ['name', 'total_images', 'num_classes', 'license']
