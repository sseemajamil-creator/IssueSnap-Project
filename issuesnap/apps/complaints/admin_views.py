"""
IssueSnap Admin Panel Views
"""
import csv
import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model

from .models import (
    Complaint, ComplaintCategory, ComplaintStatusHistory,
    DuplicateComplaintMatch, AdministratorAssignment, PriorityPrediction
)
from .forms import ComplaintStatusUpdateForm, ComplaintFilterForm
from issuesnap.apps.notifications.models import Notification
from issuesnap.apps.accounts.models import UserProfile

User = get_user_model()


def admin_required(func):
    """Decorator: requires user to be admin or staff."""
    from functools import wraps
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.is_admin_user or request.user.is_staff):
            messages.error(request, 'You do not have permission to access the admin panel.')
            return redirect('pages:home')
        return func(request, *args, **kwargs)
    return wrapper


@admin_required
def admin_dashboard(request):
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)

    complaints = Complaint.objects.all()

    stats = {
        'total': complaints.count(),
        'pending': complaints.filter(status=Complaint.PENDING).count(),
        'in_progress': complaints.filter(status__in=[Complaint.IN_PROGRESS, Complaint.PROCESSING]).count(),
        'resolved': complaints.filter(status__in=[Complaint.RESOLVED, Complaint.COMPLETED]).count(),
        'rejected': complaints.filter(status=Complaint.REJECTED).count(),
        'this_month': complaints.filter(submitted_at__gte=month_start).count(),
        'ai_analyzed': complaints.filter(ai_analyzed=True).count(),
        'duplicates': complaints.filter(is_duplicate=True).count(),
    }

    # Category statistics
    cat_stats = complaints.values('category__name', 'category__color').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # District statistics
    district_stats = complaints.values('district').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # Monthly trend (last 6 months)
    monthly_data = []
    for i in range(5, -1, -1):
        month_date = now - timedelta(days=i * 30)
        month_start_d = month_date.replace(day=1, hour=0, minute=0, second=0)
        if i > 0:
            month_end_d = (month_date + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        else:
            month_end_d = now
        count = complaints.filter(submitted_at__range=[month_start_d, month_end_d]).count()
        monthly_data.append({
            'month': month_start_d.strftime('%b %Y'),
            'count': count,
        })

    # Priority stats
    priority_stats = complaints.values('priority').annotate(count=Count('id'))

    # Recent complaints
    recent_complaints = complaints.select_related('category', 'citizen').prefetch_related('images')[:10]

    # Map data — complaints with coordinates for the dashboard map
    map_complaints = complaints.filter(
        latitude__isnull=False, longitude__isnull=False
    ).select_related('category').values(
        'complaint_id', 'title', 'category__name', 'status',
        'district', 'latitude', 'longitude'
    )[:200]
    map_complaints_json = json.dumps(list(map_complaints), default=str)

    # Pending duplicate reviews
    pending_duplicates = DuplicateComplaintMatch.objects.filter(
        is_confirmed_duplicate__isnull=True
    ).count()

    # Users
    total_users = User.objects.filter(role=User.CITIZEN).count()
    new_users_month = User.objects.filter(date_joined__gte=month_start).count()

    return render(request, 'admin_panel/dashboard.html', {
        'page_title': 'Admin Dashboard',
        'stats': stats,
        'cat_stats': json.dumps(list(cat_stats), default=str),
        'district_stats': json.dumps(list(district_stats), default=str),
        'monthly_data': json.dumps(monthly_data),
        'priority_stats': json.dumps(list(priority_stats)),
        'recent_complaints': recent_complaints,
        'map_complaints_json': map_complaints_json,
        'map_complaints_count': len(map_complaints),
        'pending_duplicates': pending_duplicates,
        'total_users': total_users,
        'new_users_month': new_users_month,
    })


@admin_required
def manage_complaints(request):
    complaints = Complaint.objects.all().select_related('category', 'citizen', 'assigned_to').prefetch_related('images')

    filter_form = ComplaintFilterForm(request.GET)
    if filter_form.is_valid():
        data = filter_form.cleaned_data
        if data.get('status'):
            complaints = complaints.filter(status=data['status'])
        if data.get('priority'):
            complaints = complaints.filter(priority=data['priority'])
        if data.get('district'):
            complaints = complaints.filter(district=data['district'])
        if data.get('category'):
            complaints = complaints.filter(category=data['category'])
        if data.get('search'):
            complaints = complaints.filter(
                Q(title__icontains=data['search']) |
                Q(description__icontains=data['search']) |
                Q(complaint_id__icontains=data['search']) |
                Q(citizen__first_name__icontains=data['search']) |
                Q(citizen__last_name__icontains=data['search'])
            )
        if data.get('date_from'):
            complaints = complaints.filter(submitted_at__date__gte=data['date_from'])
        if data.get('date_to'):
            complaints = complaints.filter(submitted_at__date__lte=data['date_to'])

    paginator = Paginator(complaints, 15)
    page = request.GET.get('page')
    complaints_page = paginator.get_page(page)

    return render(request, 'admin_panel/manage_complaints.html', {
        'page_title': 'Manage Complaints',
        'complaints': complaints_page,
        'filter_form': filter_form,
        'total_count': paginator.count,
    })


@admin_required
def admin_complaint_detail(request, complaint_id):
    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)
    form = ComplaintStatusUpdateForm(request.POST or None, instance=complaint)
    admin_users = User.objects.filter(role=User.ADMIN, is_active=True)

    if request.method == 'POST':
        if form.is_valid():
            # Capture the original status from the database BEFORE the form
            # mutates the instance. ModelForm.is_valid() copies POST data onto
            # the bound instance during full_clean(), so complaint.status is
            # already the new value after is_valid() returns. We must query
            # the DB to get the true previous status.
            original_status = Complaint.objects.filter(
                pk=complaint.pk
            ).values_list('status', flat=True).first()

            updated = form.save(commit=False)
            updated.save()

            note = request.POST.get('note', '')
            if original_status != updated.status:
                ComplaintStatusHistory.objects.create(
                    complaint=complaint,
                    old_status=original_status,
                    new_status=updated.status,
                    changed_by=request.user,
                    note=note,
                )
                # Notify citizen
                Notification.objects.create(
                    user=complaint.citizen,
                    title='Complaint Status Updated',
                    message=f'Your complaint {complaint.complaint_id} status has been updated to: {updated.get_status_display()}',
                    notification_type='status_changed',
                    complaint=complaint,
                )
            messages.success(request, 'Complaint updated successfully.')
            return redirect('admin_complaints:complaint_detail', complaint_id=complaint_id)

    status_history = complaint.status_history.select_related('changed_by').all()
    images = complaint.images.all()
    ai_results = complaint.ai_classifications.select_related('model_version').all() if hasattr(complaint, 'ai_classifications') else []
    duplicate_matches = DuplicateComplaintMatch.objects.filter(
        Q(original_complaint=complaint) | Q(duplicate_complaint=complaint)
    ).select_related('original_complaint', 'duplicate_complaint')
    priority_pred = getattr(complaint, 'priority_prediction', None)

    return render(request, 'admin_panel/complaint_detail.html', {
        'page_title': f'Complaint {complaint.complaint_id}',
        'complaint': complaint,
        'form': form,
        'status_history': status_history,
        'images': images,
        'ai_results': ai_results,
        'duplicate_matches': duplicate_matches,
        'priority_pred': priority_pred,
        'admin_users': admin_users,
    })


@admin_required
def assign_complaint(request, complaint_id):
    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)
    if request.method == 'POST':
        admin_id = request.POST.get('admin_id')
        note = request.POST.get('note', '')
        try:
            admin = User.objects.get(id=admin_id, role=User.ADMIN)
            complaint.assigned_to = admin
            complaint.save(update_fields=['assigned_to'])
            AdministratorAssignment.objects.create(
                complaint=complaint,
                assigned_to=admin,
                assigned_by=request.user,
                note=note,
            )
            Notification.objects.create(
                user=admin,
                title='Complaint Assigned',
                message=f'Complaint {complaint.complaint_id} has been assigned to you.',
                notification_type='complaint_assigned',
                complaint=complaint,
            )
            messages.success(request, f'Complaint assigned to {admin.get_full_name()}.')
        except User.DoesNotExist:
            messages.error(request, 'Selected admin not found.')
    return redirect('admin_complaints:complaint_detail', complaint_id=complaint_id)


@admin_required
def manage_users(request):
    users = User.objects.filter(role=User.CITIZEN).select_related('profile').order_by('-date_joined')

    search = request.GET.get('search', '')
    if search:
        users = users.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(username__icontains=search)
        )

    paginator = Paginator(users, 20)
    page = request.GET.get('page')
    users_page = paginator.get_page(page)

    return render(request, 'admin_panel/manage_users.html', {
        'page_title': 'Manage Users',
        'users': users_page,
        'search': search,
        'total_count': paginator.count,
    })


@admin_required
def manage_categories(request):
    categories = ComplaintCategory.objects.annotate(complaint_count=Count('complaints'))

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        slug = request.POST.get('slug', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.POST.get('icon', 'bi-exclamation-triangle')
        color = request.POST.get('color', '#2563EB')
        is_ai_supported = request.POST.get('is_ai_supported') == 'on'
        ai_class_name = request.POST.get('ai_class_name', '').strip()

        if name and slug:
            ComplaintCategory.objects.create(
                name=name, slug=slug, description=description,
                icon=icon, color=color,
                is_ai_supported=is_ai_supported, ai_class_name=ai_class_name,
            )
            messages.success(request, f'Category "{name}" created.')
        else:
            messages.error(request, 'Name and slug are required.')
        return redirect('admin_complaints:manage_categories')

    return render(request, 'admin_panel/manage_categories.html', {
        'page_title': 'Manage Categories',
        'categories': categories,
    })


@admin_required
def review_duplicates(request):
    matches = DuplicateComplaintMatch.objects.filter(
        is_confirmed_duplicate__isnull=True
    ).select_related(
        'original_complaint', 'duplicate_complaint',
        'original_complaint__category', 'duplicate_complaint__category',
        'original_complaint__citizen', 'duplicate_complaint__citizen',
    ).order_by('-similarity_score')

    paginator = Paginator(matches, 10)
    page = request.GET.get('page')
    matches_page = paginator.get_page(page)

    return render(request, 'admin_panel/review_duplicates.html', {
        'page_title': 'Review Duplicate Complaints',
        'matches': matches_page,
        'total_pending': paginator.count,
    })


@admin_required
def resolve_duplicate(request, match_id):
    match = get_object_or_404(DuplicateComplaintMatch, id=match_id)
    if request.method == 'POST':
        decision = request.POST.get('decision')
        if decision == 'confirm':
            match.is_confirmed_duplicate = True
            match.duplicate_complaint.is_duplicate = True
            match.duplicate_complaint.duplicate_of = match.original_complaint
            match.duplicate_complaint.save(update_fields=['is_duplicate', 'duplicate_of'])
        elif decision == 'reject':
            match.is_confirmed_duplicate = False
        match.reviewed_by = request.user
        match.reviewed_at = timezone.now()
        match.save()
        messages.success(request, 'Duplicate review recorded.')
    return redirect('admin_complaints:review_duplicates')


@admin_required
def review_ai_results(request):
    complaints_with_ai = Complaint.objects.filter(ai_analyzed=True).select_related(
        'category', 'citizen'
    ).prefetch_related('ai_classifications', 'images').order_by('-submitted_at')

    paginator = Paginator(complaints_with_ai, 15)
    page = request.GET.get('page')
    complaints_page = paginator.get_page(page)

    return render(request, 'admin_panel/review_ai_results.html', {
        'page_title': 'Review AI Predictions',
        'complaints': complaints_page,
    })


@admin_required
def analytics_reports(request):
    complaints = Complaint.objects.all()
    now = timezone.now()

    # Monthly stats for the past 12 months
    monthly_stats = []
    for i in range(11, -1, -1):
        month_date = now - timedelta(days=i * 30)
        m_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i > 0:
            m_end = (month_date + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0) - timedelta(seconds=1)
        else:
            m_end = now
        submitted = complaints.filter(submitted_at__range=[m_start, m_end]).count()
        resolved = complaints.filter(
            submitted_at__range=[m_start, m_end],
            status__in=[Complaint.RESOLVED, Complaint.COMPLETED]
        ).count()
        monthly_stats.append({
            'month': m_start.strftime('%b %Y'),
            'submitted': submitted,
            'resolved': resolved,
        })

    # Category distribution
    cat_distribution = complaints.values('category__name', 'category__color').annotate(
        count=Count('id')
    ).order_by('-count')

    # District distribution
    district_distribution = complaints.values('district').annotate(
        count=Count('id')
    ).order_by('-count')

    # Status distribution
    status_distribution = complaints.values('status').annotate(count=Count('id'))

    # Priority distribution
    priority_distribution = complaints.values('priority').annotate(count=Count('id'))

    return render(request, 'admin_panel/analytics_reports.html', {
        'page_title': 'Analytics & Reports',
        'monthly_stats': json.dumps(monthly_stats),
        'cat_distribution': json.dumps(list(cat_distribution), default=str),
        'district_distribution': json.dumps(list(district_distribution), default=str),
        'status_distribution': json.dumps(list(status_distribution)),
        'priority_distribution': json.dumps(list(priority_distribution)),
        'total_complaints': complaints.count(),
        'total_resolved': complaints.filter(status__in=[Complaint.RESOLVED, Complaint.COMPLETED]).count(),
        'resolution_rate': round(
            complaints.filter(status__in=[Complaint.RESOLVED, Complaint.COMPLETED]).count() /
            max(complaints.count(), 1) * 100, 1
        ),
    })


@admin_required
def export_complaints_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="issuesnap_complaints_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Complaint ID', 'Title', 'Category', 'Status', 'Priority',
        'Citizen Name', 'Citizen Email', 'District', 'Area', 'Address',
        'Submitted At', 'Updated At', 'Resolved At',
        'AI Analyzed', 'Is Duplicate',
    ])

    complaints = Complaint.objects.all().select_related('category', 'citizen').order_by('-submitted_at')

    # Apply filters if provided
    status = request.GET.get('status')
    district = request.GET.get('district')
    if status:
        complaints = complaints.filter(status=status)
    if district:
        complaints = complaints.filter(district=district)

    for c in complaints:
        writer.writerow([
            c.complaint_id, c.title,
            c.category.name if c.category else '',
            c.get_status_display(), c.get_priority_display(),
            c.citizen.get_full_name(), c.citizen.email,
            c.district, c.area, c.address,
            c.submitted_at.strftime('%Y-%m-%d %H:%M'),
            c.updated_at.strftime('%Y-%m-%d %H:%M'),
            c.resolved_at.strftime('%Y-%m-%d %H:%M') if c.resolved_at else '',
            'Yes' if c.ai_analyzed else 'No',
            'Yes' if c.is_duplicate else 'No',
        ])

    return response
