"""
IssueSnap Public Pages Views
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse

from .models import ContactMessage
from issuesnap.apps.complaints.models import Complaint, ComplaintCategory


def home(request):
    # Live stats
    stats = {
        'total_reported': Complaint.objects.count(),
        'resolved': Complaint.objects.filter(status__in=[Complaint.RESOLVED, Complaint.COMPLETED]).count(),
        'categories': ComplaintCategory.objects.filter(is_active=True).count(),
        'in_progress': Complaint.objects.filter(status=Complaint.IN_PROGRESS).count(),
    }

    recent_resolved = Complaint.objects.filter(
        status__in=[Complaint.RESOLVED, Complaint.COMPLETED]
    ).select_related('category').prefetch_related('images').order_by('-resolved_at')[:6]

    categories = ComplaintCategory.objects.filter(is_active=True).annotate(
        complaint_count=Count('complaints')
    ).order_by('-complaint_count')[:8]

    return render(request, 'pages/home.html', {
        'page_title': 'IssueSnap - AI-Powered Civic Issue Reporting',
        'stats': stats,
        'recent_resolved': recent_resolved,
        'categories': categories,
    })


def about(request):
    return render(request, 'pages/about.html', {'page_title': 'About IssueSnap'})


def how_it_works(request):
    return render(request, 'pages/how_it_works.html', {'page_title': 'How It Works'})


def ai_technology(request):
    from issuesnap.apps.ai_engine.models import ModelVersion
    active_model = ModelVersion.objects.filter(is_active=True).first()
    return render(request, 'pages/ai_technology.html', {
        'page_title': 'AI Technology',
        'active_model': active_model,
    })


def faq(request):
    return render(request, 'pages/faq.html', {'page_title': 'Frequently Asked Questions'})


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        if all([name, email, subject, message]):
            ContactMessage.objects.create(
                name=name, email=email, subject=subject, message=message
            )
            messages.success(request, 'Your message has been sent successfully. We will get back to you within 24 hours.')
            return redirect('pages:contact')
        else:
            messages.error(request, 'Please fill in all required fields.')

    return render(request, 'pages/contact.html', {'page_title': 'Contact Us'})


def privacy_policy(request):
    return render(request, 'pages/privacy_policy.html', {'page_title': 'Privacy Policy'})


def terms_conditions(request):
    return render(request, 'pages/terms_conditions.html', {'page_title': 'Terms & Conditions'})


def error_404(request, exception):
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    return render(request, 'errors/500.html', status=500)
