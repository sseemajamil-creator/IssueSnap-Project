"""
IssueSnap Accounts Models
Custom User model with extended profile
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError(_('Email address is required'))
        if not username:
            raise ValueError(_('Username is required'))
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.ADMIN)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    CITIZEN = 'citizen'
    ADMIN = 'admin'
    RESEARCHER = 'researcher'
    ROLE_CHOICES = [
        (CITIZEN, 'Citizen'),
        (ADMIN, 'Administrator'),
        (RESEARCHER, 'Researcher'),
    ]

    email = models.EmailField(_('email address'), unique=True)
    username = models.CharField(_('username'), max_length=50, unique=True)
    first_name = models.CharField(_('first name'), max_length=100)
    last_name = models.CharField(_('last name'), max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=CITIZEN)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        db_table = 'users'
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        return f'{self.get_full_name()} ({self.email})'

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_citizen(self):
        return self.role == self.CITIZEN

    @property
    def is_admin_user(self):
        return self.role == self.ADMIN

    @property
    def is_researcher(self):
        return self.role == self.RESEARCHER


DISTRICT_CHOICES = [
    ('karachi', 'Karachi'),
    ('lahore', 'Lahore'),
    ('islamabad', 'Islamabad'),
    ('rawalpindi', 'Rawalpindi'),
    ('faisalabad', 'Faisalabad'),
    ('multan', 'Multan'),
    ('peshawar', 'Peshawar'),
    ('quetta', 'Quetta'),
    ('sialkot', 'Sialkot'),
    ('gujranwala', 'Gujranwala'),
    ('other', 'Other'),
]


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    district = models.CharField(max_length=100, choices=DISTRICT_CHOICES, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    bio = models.TextField(blank=True, max_length=500)
    avatar = models.ImageField(upload_to='profiles/avatars/', blank=True, null=True)
    cnic = models.CharField(max_length=15, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'

    def __str__(self):
        return f'Profile: {self.user.get_full_name()}'

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return '/static/images/default-avatar.png'


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'password_reset_tokens'

    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and self.expires_at > timezone.now()
