"""
IssueSnap Create Admin User Script
=====================================
Creates a default administrator account.

Usage:
  python scripts/create_admin.py

Change the credentials in this script or use django's createsuperuser command.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'issuesnap.config.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
from issuesnap.apps.accounts.models import UserProfile

User = get_user_model()

ADMIN_EMAIL    = 'admin@issuesnap.com'
ADMIN_USERNAME = 'admin'
ADMIN_FNAME    = 'IssueSnap'
ADMIN_LNAME    = 'Administrator'
ADMIN_PASSWORD = 'Admin@2026!'  # Change immediately after first login

def create_admin():
    if User.objects.filter(email=ADMIN_EMAIL).exists():
        print(f"[INFO] Admin account already exists: {ADMIN_EMAIL}")
        return

    user = User.objects.create_superuser(
        email=ADMIN_EMAIL,
        username=ADMIN_USERNAME,
        first_name=ADMIN_FNAME,
        last_name=ADMIN_LNAME,
        password=ADMIN_PASSWORD,
    )
    UserProfile.objects.get_or_create(user=user)
    print(f"[OK] Admin created:")
    print(f"     Email:    {ADMIN_EMAIL}")
    print(f"     Password: {ADMIN_PASSWORD}")
    print(f"     !! Change the password immediately after first login !!")


if __name__ == '__main__':
    create_admin()
