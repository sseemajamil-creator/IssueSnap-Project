"""Seed initial data: categories + admin user."""
import os, sys
sys.path.insert(0, str(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'issuesnap.config.settings')
import django; django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()
from issuesnap.apps.complaints.models import ComplaintCategory

categories = [
    dict(name='Road Pothole', slug='pothole', description='Holes, craters or depressions in road surfaces', icon='bi-exclamation-triangle-fill', color='#EF4444', is_ai_supported=True, ai_class_name='pothole', order=1),
    dict(name='Road Crack', slug='road-crack', description='Cracks, fractures or breaks in road pavement', icon='bi-diamond-half', color='#F59E0B', is_ai_supported=True, ai_class_name='road_crack', order=2),
    dict(name='Garbage Overflow', slug='garbage', description='Overflowing bins, illegal dumping, litter accumulation', icon='bi-trash3-fill', color='#10B981', is_ai_supported=True, ai_class_name='garbage', order=3),
    dict(name='Water Leakage', slug='water-leakage', description='Burst pipes, water leaks, flooding', icon='bi-droplet-half', color='#06B6D4', is_ai_supported=True, ai_class_name='water_leakage', order=4),
    dict(name='Drainage Blockage', slug='drainage-blockage', description='Blocked drains, clogged sewers, stagnant water', icon='bi-water', color='#8B5CF6', is_ai_supported=True, ai_class_name='drainage_blockage', order=5),
    dict(name='Broken Streetlight', slug='broken-streetlight', description='Non-functional street lights, broken lamp posts', icon='bi-lamp-fill', color='#F59E0B', is_ai_supported=True, ai_class_name='broken_streetlight', order=6),
    dict(name='Damaged Infrastructure', slug='damaged-infrastructure', description='Damaged walls, bridges, public structures', icon='bi-building-x', color='#6B7280', is_ai_supported=True, ai_class_name='damaged_infrastructure', order=7),
    dict(name='Other', slug='other', description='Other civic issues not covered above', icon='bi-three-dots', color='#374151', is_ai_supported=False, ai_class_name='', order=8),
]

created = 0
for c in categories:
    obj, was = ComplaintCategory.objects.get_or_create(slug=c['slug'], defaults=c)
    if was: created += 1
print(f"Categories: {created} created, {len(categories)-created} already existed")

# Create admin user
admin_email = 'admin@issuesnap.com'
if not User.objects.filter(email=admin_email).exists():
    User.objects.create_superuser(
        email=admin_email, username='admin',
        password='AdminPass2026!',
        first_name='Admin', last_name='User'
    )
    User.objects.filter(email=admin_email).update(role='admin')
    print(f"Admin created: {admin_email} / AdminPass2026!")
else:
    u = User.objects.get(email=admin_email)
    u.role = 'admin'; u.is_staff=True; u.is_superuser=True
    u.save(update_fields=['role','is_staff','is_superuser'])
    print(f"Admin exists: {admin_email}")

# Create demo citizen
demo_email = 'citizen@issuesnap.com'
if not User.objects.filter(email=demo_email).exists():
    c = User.objects.create_user(
        email=demo_email, username='citizen', password='CitizenPass2026!',
        first_name='Demo', last_name='Citizen'
    )
    print(f"Citizen created: {demo_email} / CitizenPass2026!")
else:
    print(f"Citizen exists: {demo_email}")

print("\nDone. Login URLs:")
print("  Admin:    http://127.0.0.1:8000/accounts/login/  (admin@issuesnap.com / AdminPass2026!)")
print("  Citizen:  http://127.0.0.1:8000/accounts/login/  (citizen@issuesnap.com / CitizenPass2026!)")
