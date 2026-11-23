"""
IssueSnap Database Setup Script
=================================
Creates the MySQL database and populates initial data.

Usage:
  python scripts/setup_database.py

Requirements:
  - MySQL running with credentials in .env
  - pip install mysqlclient python-decouple
"""

import os
import sys
from pathlib import Path

# Setup Django
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'issuesnap.config.settings')

import django
django.setup()

from django.db import connection
from decouple import config
import pymysql


def create_database():
    db_name = config('DB_NAME', default='issuesnap_db')
    db_user = config('DB_USER', default='root')
    db_pass = config('DB_PASSWORD', default='')
    db_host = config('DB_HOST', default='localhost')
    db_port = config('DB_PORT', default=3306, cast=int)

    print(f"[INFO] Creating database '{db_name}' on {db_host}:{db_port}...")

    try:
        conn = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_pass,
            charset='utf8mb4',
        )
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[OK] Database '{db_name}' created/verified.")
    except Exception as e:
        print(f"[ERROR] Database creation failed: {e}")
        print("Make sure MySQL is running and credentials are correct in .env")
        return False
    return True


def run_migrations():
    from django.core.management import call_command
    print("\n[INFO] Running migrations...")
    try:
        call_command('makemigrations', '--no-input')
        call_command('migrate', '--no-input')
        print("[OK] Migrations complete.")
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return False
    return True


def create_initial_data():
    from issuesnap.apps.complaints.models import ComplaintCategory

    print("\n[INFO] Creating initial complaint categories...")

    categories = [
        {
            'name': 'Road Pothole',
            'slug': 'pothole',
            'description': 'Holes, craters or depressions in road surfaces',
            'icon': 'bi-exclamation-triangle-fill',
            'color': '#EF4444',
            'is_ai_supported': True,
            'ai_class_name': 'pothole',
            'order': 1,
        },
        {
            'name': 'Road Crack',
            'slug': 'road-crack',
            'description': 'Cracks, fractures or breaks in road pavement',
            'icon': 'bi-diamond-half',
            'color': '#F59E0B',
            'is_ai_supported': True,
            'ai_class_name': 'road_crack',
            'order': 2,
        },
        {
            'name': 'Garbage Overflow',
            'slug': 'garbage',
            'description': 'Overflowing bins, illegal dumping, litter accumulation',
            'icon': 'bi-trash3-fill',
            'color': '#10B981',
            'is_ai_supported': True,
            'ai_class_name': 'garbage',
            'order': 3,
        },
        {
            'name': 'Water Leakage',
            'slug': 'water-leakage',
            'description': 'Burst pipes, water leaks, flooding',
            'icon': 'bi-droplet-half',
            'color': '#06B6D4',
            'is_ai_supported': True,
            'ai_class_name': 'water_leakage',
            'order': 4,
        },
        {
            'name': 'Drainage Blockage',
            'slug': 'drainage-blockage',
            'description': 'Blocked drains, clogged sewers, stagnant water',
            'icon': 'bi-water',
            'color': '#8B5CF6',
            'is_ai_supported': True,
            'ai_class_name': 'drainage_blockage',
            'order': 5,
        },
        {
            'name': 'Broken Streetlight',
            'slug': 'broken-streetlight',
            'description': 'Non-functional street lights, broken lamp posts',
            'icon': 'bi-lamp-fill',
            'color': '#F59E0B',
            'is_ai_supported': True,
            'ai_class_name': 'broken_streetlight',
            'order': 6,
        },
        {
            'name': 'Damaged Infrastructure',
            'slug': 'damaged-infrastructure',
            'description': 'Damaged walls, bridges, public structures',
            'icon': 'bi-building-x',
            'color': '#6B7280',
            'is_ai_supported': True,
            'ai_class_name': 'damaged_infrastructure',
            'order': 7,
        },
        {
            'name': 'Other',
            'slug': 'other',
            'description': 'Other civic issues not covered above',
            'icon': 'bi-three-dots',
            'color': '#374151',
            'is_ai_supported': False,
            'ai_class_name': '',
            'order': 8,
        },
    ]

    created = 0
    for cat_data in categories:
        cat, was_created = ComplaintCategory.objects.get_or_create(
            slug=cat_data['slug'],
            defaults=cat_data
        )
        if was_created:
            created += 1
            print(f"  [+] {cat.name}")
        else:
            print(f"  [=] {cat.name} (already exists)")

    print(f"[OK] {created} new categories created.")


def create_superuser_prompt():
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if User.objects.filter(role='admin').exists():
        print("\n[INFO] Admin user already exists.")
        return

    print("\n[INFO] No admin user found.")
    print("Run: python manage.py createsuperuser")
    print("Or use the Django admin at /django-admin/ to create one.")


if __name__ == '__main__':
    print("=" * 60)
    print("IssueSnap Database Setup")
    print("=" * 60)

    if not create_database():
        sys.exit(1)

    if not run_migrations():
        sys.exit(1)

    create_initial_data()
    create_superuser_prompt()

    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Create admin: python manage.py createsuperuser")
    print("  2. Start server: python manage.py runserver")
    print("  3. Access: http://localhost:8000/")
    print("  4. Admin panel: http://localhost:8000/admin-panel/dashboard/")
