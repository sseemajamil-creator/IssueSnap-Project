"""
IssueSnap Complaint Forms
"""
from django import forms
from django.conf import settings
from .models import Complaint, ComplaintCategory, DISTRICT_CHOICES


class MultipleFileInput(forms.FileInput):
    """Custom widget that allows multiple file uploads in Django 6+."""
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        default_attrs = {'multiple': True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class MultipleFileField(forms.FileField):
    """FileField that accepts multiple files."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png,image/webp',
            'id': 'complaint-images',
        }))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # For multi-file, data may be a list
        if isinstance(data, list):
            result = []
            for d in data:
                result.append(super().clean(d, initial))
            return result
        return super().clean(data, initial)


class ComplaintSubmissionForm(forms.ModelForm):
    images = MultipleFileField(
        required=True,
        label='Upload Images (1-5 images, max 10MB each)'
    )


    latitude = forms.DecimalField(
        widget=forms.HiddenInput(),
        required=False,
        max_digits=10,
        decimal_places=7,
    )
    longitude = forms.DecimalField(
        widget=forms.HiddenInput(),
        required=False,
        max_digits=10,
        decimal_places=7,
    )

    class Meta:
        model = Complaint
        fields = [
            'title', 'description', 'category',
            'district', 'area', 'address', 'landmark',
            'latitude', 'longitude'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Large pothole on Main Boulevard causing accidents',
                'maxlength': '200',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe the issue in detail...',
                'rows': 5,
            }),
            'category': forms.Select(attrs={'class': 'form-select', 'id': 'id_category'}),
            'district': forms.Select(attrs={'class': 'form-select'}),
            'area': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. DHA Phase 5, Gulshan-e-Iqbal',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Full address of the issue location',
                'rows': 3,
            }),
            'landmark': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nearby landmark (optional)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ComplaintCategory.objects.filter(is_active=True)
        self.fields['category'].empty_label = 'Select a category'

    def clean_images(self):
        # Note: multi-file handled in view via request.FILES.getlist
        return self.cleaned_data.get('images')

    def clean_title(self):
        title = self.cleaned_data.get('title', '')
        if len(title.strip()) < 10:
            raise forms.ValidationError('Title must be at least 10 characters.')
        return title.strip()

    def clean_description(self):
        desc = self.cleaned_data.get('description', '')
        if len(desc.strip()) < 20:
            raise forms.ValidationError('Description must be at least 20 characters.')
        return desc.strip()

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')
        # Location is mandatory — the user must pin a spot on the map.
        if not latitude or not longitude:
            raise forms.ValidationError(
                'Please select a location on the map before submitting your complaint.'
            )
        return cleaned_data


class ComplaintStatusUpdateForm(forms.ModelForm):
    note = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Add a note...'}),
        required=False,
        label='Status Note'
    )

    class Meta:
        model = Complaint
        fields = ['status', 'priority', 'admin_notes', 'rejection_reason']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'admin_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'rejection_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ComplaintFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Complaint.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    priority = forms.ChoiceField(
        choices=[('', 'All Priorities')] + Complaint.PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    district = forms.ChoiceField(
        choices=[('', 'All Districts')] + DISTRICT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    category = forms.ModelChoiceField(
        queryset=ComplaintCategory.objects.filter(is_active=True),
        required=False,
        empty_label='All Categories',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Search complaints...'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
