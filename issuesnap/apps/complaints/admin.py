from django.contrib import admin
from .models import (
    ComplaintCategory, Complaint, ComplaintImage,
    ComplaintStatusHistory, DuplicateComplaintMatch, PriorityPrediction,
    AdministratorAssignment
)


@admin.register(ComplaintCategory)
class ComplaintCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_ai_supported', 'is_active', 'order']
    list_filter = ['is_ai_supported', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


class ComplaintImageInline(admin.TabularInline):
    model = ComplaintImage
    extra = 0
    readonly_fields = ['uploaded_at', 'file_size']


class StatusHistoryInline(admin.TabularInline):
    model = ComplaintStatusHistory
    extra = 0
    readonly_fields = ['changed_at']


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ['complaint_id', 'title', 'category', 'status', 'priority', 'citizen', 'district', 'submitted_at']
    list_filter = ['status', 'priority', 'district', 'category', 'ai_analyzed', 'is_duplicate']
    search_fields = ['complaint_id', 'title', 'citizen__email', 'citizen__first_name', 'citizen__last_name']
    readonly_fields = ['complaint_id', 'submitted_at', 'updated_at']
    inlines = [ComplaintImageInline, StatusHistoryInline]
    ordering = ['-submitted_at']


@admin.register(DuplicateComplaintMatch)
class DuplicateComplaintMatchAdmin(admin.ModelAdmin):
    list_display = ['original_complaint', 'duplicate_complaint', 'similarity_score', 'is_confirmed_duplicate', 'detected_at']
    list_filter = ['is_confirmed_duplicate', 'category_match']


@admin.register(PriorityPrediction)
class PriorityPredictionAdmin(admin.ModelAdmin):
    list_display = ['complaint', 'predicted_priority', 'method', 'created_at']
