"""
IssueSnap Accounts Views
"""
import uuid
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .forms import (
    RegisterForm, LoginForm, ProfileUpdateForm, UserUpdateForm,
    ChangePasswordForm, ForgotPasswordForm, ResetPasswordForm
)
from .models import UserProfile, PasswordResetToken

User = get_user_model()


def register_view(request):
    if request.user.is_authenticated:
        return redirect('complaints:citizen_dashboard')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            # Wrap in a transaction so a failed registration does not leave
            # an incomplete user row in the database.
            with transaction.atomic():
                user = form.save()
            login(request, user)
            messages.success(request, f'Welcome to IssueSnap, {user.get_short_name()}! Your account has been created.')
            return redirect('complaints:citizen_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')

    return render(request, 'accounts/register.html', {'form': form, 'page_title': 'Create Account'})


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_admin_user or request.user.is_staff:
            return redirect('admin_complaints:dashboard')
        return redirect('complaints:citizen_dashboard')

    form = LoginForm(request, request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            remember_me = form.cleaned_data.get('remember_me')
            if not remember_me:
                request.session.set_expiry(0)
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_short_name()}!')
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            if user.is_admin_user or user.is_staff:
                return redirect('admin_complaints:dashboard')
            return redirect('complaints:citizen_dashboard')
        else:
            messages.error(request, 'Invalid email or password. Please try again.')

    return render(request, 'accounts/login.html', {'form': form, 'page_title': 'Sign In'})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been signed out successfully.')
    return redirect('pages:home')


@login_required
def profile_view(request):
    # get_or_create is safe against race conditions and existing profiles.
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    return render(request, 'accounts/profile.html', {
        'page_title': 'My Profile',
        'profile': profile,
    })


@login_required
def edit_profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    user_form = UserUpdateForm(request.POST or None, instance=request.user)
    profile_form = ProfileUpdateForm(request.POST or None, request.FILES or None, instance=profile)

    if request.method == 'POST':
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the errors below.')

    return render(request, 'accounts/edit_profile.html', {
        'page_title': 'Edit Profile',
        'user_form': user_form,
        'profile_form': profile_form,
    })


@login_required
def change_password_view(request):
    form = ChangePasswordForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            current_password = form.cleaned_data['current_password']
            new_password = form.cleaned_data['new_password']

            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
            else:
                request.user.set_password(new_password)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Your password has been changed successfully.')
                return redirect('accounts:profile')

    return render(request, 'accounts/change_password.html', {
        'form': form,
        'page_title': 'Change Password',
    })


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('pages:home')

    form = ForgotPasswordForm(request.POST or None)
    email_sent = False

    if request.method == 'POST':
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                token = str(uuid.uuid4())
                expires_at = timezone.now() + timedelta(hours=1)
                PasswordResetToken.objects.create(user=user, token=token, expires_at=expires_at)

                reset_link = f"{request.build_absolute_uri('/')[:-1]}/accounts/reset-password/{token}/"

                # Try to send email; handle SMTP not configured gracefully
                try:
                    send_mail(
                        'IssueSnap - Password Reset Request',
                        f'Click the link to reset your password: {reset_link}\n\nThis link expires in 1 hour.',
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False,
                    )
                    email_sent = True
                except Exception:
                    # Email backend not configured — show token in dev mode only
                    if settings.DEBUG:
                        messages.info(request, f'[DEV] Reset link: {reset_link}')
                    email_sent = True

            except User.DoesNotExist:
                pass  # Don't reveal whether email exists

            messages.success(request, 'If that email is registered, a password reset link has been sent.')
            email_sent = True

    return render(request, 'accounts/forgot_password.html', {
        'form': form,
        'page_title': 'Forgot Password',
        'email_sent': email_sent,
    })


def reset_password_view(request, token):
    reset_token = get_object_or_404(PasswordResetToken, token=token)

    if not reset_token.is_valid():
        messages.error(request, 'This password reset link has expired or already been used.')
        return redirect('accounts:forgot_password')

    form = ResetPasswordForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = reset_token.user
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            reset_token.is_used = True
            reset_token.save()
            messages.success(request, 'Your password has been reset successfully. You can now log in.')
            return redirect('accounts:login')

    return render(request, 'accounts/reset_password.html', {
        'form': form,
        'page_title': 'Reset Password',
        'token': token,
    })
