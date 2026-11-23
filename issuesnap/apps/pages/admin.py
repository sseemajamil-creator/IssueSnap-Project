from django.contrib import admin
from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'is_replied', 'created_at']
    list_filter = ['is_replied']
    search_fields = ['name', 'email', 'subject']
