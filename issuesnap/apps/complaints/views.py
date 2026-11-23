"""
IssueSnap Citizen Complaint Views
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import (
    Complaint, ComplaintImage, ComplaintCategory,
    ComplaintStatusHistory, DuplicateComplaintMatch
)
from .forms import ComplaintSubmissionForm, ComplaintFilterForm
from issuesnap.apps.notifications.models import Notification
from issuesnap.apps.ai_engine.tasks import analyze_complaint_images, detect_duplicates, predict_priority


@login_required
def citizen_dashboard(request):
    user = request.user
    complaints = Complaint.objects.filter(citizen=user)

    stats = {
        'total': complaints.count(),
        'pending': complaints.filter(status=Complaint.PENDING).count(),
        'in_progress': complaints.filter(status__in=[Complaint.IN_PROGRESS, Complaint.PROCESSING]).count(),
        'resolved': complaints.filter(status__in=[Complaint.RESOLVED, Complaint.COMPLETED]).count(),
        'rejected': complaints.filter(status=Complaint.REJECTED).count(),
    }

    recent_complaints = complaints.select_related('category').prefetch_related('images')[:5]
    recent_notifications = Notification.objects.filter(user=user, is_read=False)[:5]

    categories = ComplaintCategory.objects.filter(is_active=True)

    return render(request, 'complaints/citizen_dashboard.html', {
        'page_title': 'My Dashboard',
        'stats': stats,
        'recent_complaints': recent_complaints,
        'recent_notifications': recent_notifications,
        'categories': categories,
    })


@login_required
def report_issue(request):
    form = ComplaintSubmissionForm(request.POST or None, request.FILES or None)
    categories = ComplaintCategory.objects.filter(is_active=True)

    if request.method == 'POST':
        images = request.FILES.getlist('images')

        if not images:
            messages.error(request, 'Please upload at least one image of the issue.')
            return render(request, 'complaints/report_issue.html', {
                'form': form, 'categories': categories, 'page_title': 'Report an Issue'
            })

        if len(images) > 5:
            messages.error(request, 'You can upload a maximum of 5 images.')
            return render(request, 'complaints/report_issue.html', {
                'form': form, 'categories': categories, 'page_title': 'Report an Issue'
            })

        # Validate image types and sizes
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        max_size = 10 * 1024 * 1024

        for img in images:
            if img.content_type not in allowed_types:
                messages.error(request, f'File "{img.name}" is not a valid image. Allowed: JPEG, PNG, WebP.')
                return render(request, 'complaints/report_issue.html', {
                    'form': form, 'categories': categories, 'page_title': 'Report an Issue'
                })
            if img.size > max_size:
                messages.error(request, f'File "{img.name}" exceeds the 10MB limit.')
                return render(request, 'complaints/report_issue.html', {
                    'form': form, 'categories': categories, 'page_title': 'Report an Issue'
                })

        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.citizen = request.user
            complaint.save()

            # Save images
            for idx, img in enumerate(images):
                ComplaintImage.objects.create(
                    complaint=complaint,
                    image=img,
                    is_primary=(idx == 0),
                    file_size=img.size,
                )

            # Create initial status history
            ComplaintStatusHistory.objects.create(
                complaint=complaint,
                old_status='',
                new_status=Complaint.PENDING,
                changed_by=request.user,
                note='Complaint submitted by citizen.',
            )

            # Notify user
            Notification.objects.create(
                user=request.user,
                title='Complaint Submitted',
                message=f'Your complaint {complaint.complaint_id} has been submitted successfully. AI analysis will begin shortly.',
                notification_type='complaint_submitted',
                complaint=complaint,
            )

            # Trigger AI analysis (graceful failure)
            try:
                analyze_complaint_images(complaint.id)
            except Exception as e:
                pass  # AI failures must not block submission

            # Duplicate detection
            try:
                detect_duplicates(complaint.id)
            except Exception:
                pass

            # Priority prediction
            try:
                predict_priority(complaint.id)
            except Exception:
                pass

            messages.success(
                request,
                f'Your complaint has been submitted successfully! '
                f'Complaint ID: <strong>{complaint.complaint_id}</strong>. '
                f'AI analysis is in progress.',
            )
            return redirect('complaints:complaint_detail', complaint_id=complaint.complaint_id)
        else:
            messages.error(request, 'Please correct the errors below.')

    return render(request, 'complaints/report_issue.html', {
        'form': form,
        'categories': categories,
        'page_title': 'Report an Issue',
    })


@login_required
def my_complaints(request):
    complaints = Complaint.objects.filter(
        citizen=request.user
    ).select_related('category').prefetch_related('images')

    filter_form = ComplaintFilterForm(request.GET)
    if filter_form.is_valid():
        data = filter_form.cleaned_data
        if data.get('status'):
            complaints = complaints.filter(status=data['status'])
        if data.get('priority'):
            complaints = complaints.filter(priority=data['priority'])
        if data.get('category'):
            complaints = complaints.filter(category=data['category'])
        if data.get('search'):
            complaints = complaints.filter(
                Q(title__icontains=data['search']) |
                Q(description__icontains=data['search']) |
                Q(complaint_id__icontains=data['search'])
            )
        if data.get('date_from'):
            complaints = complaints.filter(submitted_at__date__gte=data['date_from'])
        if data.get('date_to'):
            complaints = complaints.filter(submitted_at__date__lte=data['date_to'])

    paginator = Paginator(complaints, 10)
    page = request.GET.get('page')
    complaints_page = paginator.get_page(page)

    return render(request, 'complaints/my_complaints.html', {
        'page_title': 'My Complaints',
        'complaints': complaints_page,
        'filter_form': filter_form,
        'total_count': paginator.count,
    })


@login_required
def complaint_detail(request, complaint_id):
    complaint = get_object_or_404(
        Complaint,
        complaint_id=complaint_id,
        citizen=request.user
    )
    complaint.view_count += 1
    complaint.save(update_fields=['view_count'])

    status_history = complaint.status_history.select_related('changed_by').all()
    images = complaint.images.all()
    ai_results = getattr(complaint, 'ai_classifications', None)
    if ai_results:
        ai_results = ai_results.select_related('model_version').all()
    duplicate_matches = DuplicateComplaintMatch.objects.filter(
        Q(original_complaint=complaint) | Q(duplicate_complaint=complaint)
    ).select_related('original_complaint', 'duplicate_complaint')

    return render(request, 'complaints/complaint_detail.html', {
        'page_title': f'Complaint {complaint.complaint_id}',
        'complaint': complaint,
        'status_history': status_history,
        'images': images,
        'ai_results': ai_results,
        'duplicate_matches': duplicate_matches,
    })


@login_required
def track_complaint(request):
    complaint = None
    complaint_id = request.GET.get('complaint_id', '').strip().upper()

    if complaint_id:
        try:
            complaint = Complaint.objects.get(
                complaint_id=complaint_id,
                citizen=request.user
            )
        except Complaint.DoesNotExist:
            messages.error(request, f'No complaint found with ID: {complaint_id}')

    return render(request, 'complaints/track_complaint.html', {
        'page_title': 'Track Complaint',
        'complaint': complaint,
        'searched_id': complaint_id,
    })


@login_required
def complaint_history(request):
    complaints = Complaint.objects.filter(
        citizen=request.user,
        status__in=[Complaint.RESOLVED, Complaint.COMPLETED, Complaint.REJECTED]
    ).select_related('category').prefetch_related('images').order_by('-updated_at')

    paginator = Paginator(complaints, 10)
    page = request.GET.get('page')
    complaints_page = paginator.get_page(page)

    return render(request, 'complaints/complaint_history.html', {
        'page_title': 'Complaint History',
        'complaints': complaints_page,
    })


def public_issues(request):
    """Public-facing map view of reported issues."""
    complaints = Complaint.objects.filter(
        status__in=[Complaint.IN_PROGRESS, Complaint.PROCESSING, Complaint.RESOLVED, Complaint.COMPLETED],
        latitude__isnull=False,
        longitude__isnull=False
    ).select_related('category').values(
        'complaint_id', 'title', 'category__name', 'status',
        'district', 'latitude', 'longitude', 'submitted_at'
    )

    categories = ComplaintCategory.objects.filter(is_active=True)
    districts = Complaint.objects.values_list('district', flat=True).distinct()

    # Category stats
    cat_stats = Complaint.objects.values('category__name').annotate(count=Count('id')).order_by('-count')[:10]

    complaints_json = json.dumps(list(complaints), default=str)

    return render(request, 'complaints/public_issues.html', {
        'page_title': 'Public Issues Map',
        'complaints_json': complaints_json,
        'categories': categories,
        'districts': districts,
        'cat_stats': cat_stats,
        'total_public': complaints.count(),
    })
