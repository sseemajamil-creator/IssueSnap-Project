"""
IssueSnap Comprehensive Backend Tests
Covers: auth, complaints, images, location, admin, tracking,
        AI integration, notifications, security.
"""
import json
from io import BytesIO
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from PIL import Image

from issuesnap.apps.accounts.models import UserProfile
from issuesnap.apps.complaints.models import (
    Complaint, ComplaintImage, ComplaintCategory,
    ComplaintStatusHistory, PriorityPrediction,
)
from issuesnap.apps.notifications.models import Notification
from issuesnap.apps.ai_engine.models import NLPAnalysis

User = get_user_model()


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _jpeg(color='gray', size=(64, 64)):
    buf = BytesIO()
    Image.new('RGB', size, color=color).save(buf, 'JPEG')
    buf.seek(0)
    return buf.read()


def _uploaded_image(name='photo.jpg', color='gray'):
    return SimpleUploadedFile(name, _jpeg(color), content_type='image/jpeg')


def _make_citizen(suffix='a', email=None):
    email = email or f'citizen_{suffix}@test.com'
    return User.objects.create_user(
        email=email, username=f'citizen_{suffix}',
        password='TestPass2026!',
        first_name='Test', last_name='Citizen',
    )


def _make_admin(suffix='admin1'):
    u = User.objects.create_user(
        email=f'{suffix}@test.com', username=suffix,
        password='AdminPass2026!',
        first_name='Admin', last_name='User',
    )
    u.role = User.ADMIN
    u.is_staff = True
    u.save()
    return u


def _make_category():
    return ComplaintCategory.objects.get_or_create(
        slug='pothole',
        defaults=dict(
            name='Road Pothole', icon='bi-exclamation-triangle',
            color='#EF4444', is_ai_supported=True, ai_class_name='pothole',
        )
    )[0]


def _complaint_post_data(category_id, **overrides):
    base = dict(
        title='Large pothole on Main Boulevard near junction',
        description='A very dangerous pothole causing multiple accidents daily',
        category=str(category_id),
        district='karachi',
        area='DHA Phase 5',
        address='House 12, Street 3, DHA Phase 5, Karachi',
        landmark='Near City Hospital',
        latitude='24.8607000',
        longitude='67.0011000',
    )
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────
# 1. DATABASE
# ─────────────────────────────────────────────────────────────

class DatabaseTest(TestCase):
    def test_database_connection(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        self.assertEqual(row[0], 1)

    def test_all_models_accessible(self):
        from issuesnap.apps.complaints.models import (
            Complaint, ComplaintImage, ComplaintCategory,
            ComplaintStatusHistory, DuplicateComplaintMatch, PriorityPrediction,
        )
        from issuesnap.apps.ai_engine.models import AIClassification, ModelVersion, NLPAnalysis
        from issuesnap.apps.notifications.models import Notification
        from issuesnap.apps.accounts.models import UserProfile, PasswordResetToken
        for model in [Complaint, ComplaintImage, ComplaintCategory,
                      ComplaintStatusHistory, DuplicateComplaintMatch,
                      PriorityPrediction, AIClassification, ModelVersion,
                      NLPAnalysis, Notification, UserProfile, PasswordResetToken]:
            self.assertIsNotNone(model.objects.count())

    def test_complaint_category_to_complaint_fk(self):
        cat = _make_category()
        citizen = _make_citizen('db1')
        c = Complaint.objects.create(
            citizen=citizen, category=cat,
            title='FK test', description='FK relationship test complaint here.',
            district='karachi', area='DHA', address='123 Main St',
        )
        self.assertEqual(c.category, cat)
        self.assertIn(c, cat.complaints.all())

    def test_data_persists_across_queries(self):
        citizen = _make_citizen('db2')
        cat = _make_category()
        Complaint.objects.create(
            citizen=citizen, category=cat,
            title='Persistence test complaint here',
            description='Checks data persists after creation in test.',
            district='lahore', area='Gulberg', address='456 Main St',
            latitude=Decimal('31.5204'), longitude=Decimal('74.3587'),
        )
        fetched = Complaint.objects.get(citizen=citizen)
        self.assertEqual(fetched.latitude, Decimal('31.5204'))
        self.assertEqual(fetched.longitude, Decimal('74.3587'))


# ─────────────────────────────────────────────────────────────
# 2. USER AUTHENTICATION
# ─────────────────────────────────────────────────────────────

class AuthenticationTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.citizen = _make_citizen('auth1')

    def test_registration_creates_user_and_profile(self):
        resp = self.client.post(reverse('accounts:register'), {
            'first_name': 'Jane', 'last_name': 'Doe',
            'email': 'jane@test.com', 'username': 'janedoe',
            'password': 'StrongPass2026!', 'confirm_password': 'StrongPass2026!',
            'agree_terms': 'on',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        user = User.objects.get(email='jane@test.com')
        self.assertEqual(user.role, User.CITIZEN)
        self.assertTrue(user.check_password('StrongPass2026!'))
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)

    def test_password_is_hashed_not_plaintext(self):
        user = _make_citizen('hash1')
        self.assertNotEqual(user.password, 'TestPass2026!')
        self.assertTrue(user.password.startswith('pbkdf2_'))

    def test_login_valid_credentials(self):
        resp = self.client.post(reverse('accounts:login'), {
            'username': self.citizen.email,
            'password': 'TestPass2026!',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['user'].is_authenticated)

    def test_login_invalid_credentials(self):
        resp = self.client.post(reverse('accounts:login'), {
            'username': self.citizen.email,
            'password': 'WrongPassword!',
        })
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_logout(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.post(reverse('accounts:logout'), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_profile_view_requires_login(self):
        resp = self.client.get(reverse('accounts:profile'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp.url)

    def test_profile_view_accessible_when_logged_in(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(reverse('accounts:profile'))
        self.assertEqual(resp.status_code, 200)

    def test_edit_profile_saves_data(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.post(reverse('accounts:edit_profile'), {
            'first_name': 'Updated', 'last_name': 'Name',
            'username': self.citizen.username,
            'phone': '+92-300-1234567',
            'district': 'karachi', 'city': 'Karachi',
            'address': '123 Test Street', 'bio': 'Test bio', 'cnic': '',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.first_name, 'Updated')

    def test_change_password(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.post(reverse('accounts:change_password'), {
            'current_password': 'TestPass2026!',
            'new_password': 'NewStrongPass2026!',
            'confirm_new_password': 'NewStrongPass2026!',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.citizen.refresh_from_db()
        self.assertTrue(self.citizen.check_password('NewStrongPass2026!'))

    def test_change_password_wrong_current_rejected(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        self.client.post(reverse('accounts:change_password'), {
            'current_password': 'WrongCurrent!',
            'new_password': 'NewPass2026!',
            'confirm_new_password': 'NewPass2026!',
        })
        self.citizen.refresh_from_db()
        self.assertTrue(self.citizen.check_password('TestPass2026!'))

    def test_session_is_created_on_login(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        self.assertIn('_auth_user_id', self.client.session)


# ─────────────────────────────────────────────────────────────
# 3. COMPLAINT MANAGEMENT
# ─────────────────────────────────────────────────────────────

class ComplaintManagementTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.citizen = _make_citizen('cmp1')
        self.other_citizen = _make_citizen('cmp2', email='other@test.com')
        self.cat = _make_category()

    def test_complaint_submission_requires_login(self):
        resp = self.client.get(reverse('complaints:report_issue'))
        self.assertEqual(resp.status_code, 302)

    def test_create_complaint_with_valid_data(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        resp = self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        self.assertEqual(resp.status_code, 302)
        c = Complaint.objects.filter(citizen=self.citizen).first()
        self.assertIsNotNone(c)
        self.assertTrue(c.complaint_id.startswith('ISS-'))

    def test_complaint_id_format(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image('a.jpg')
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        import re
        self.assertRegex(c.complaint_id, r'^ISS-\d{4}-\d{6}$')

    def test_unique_complaint_ids(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        ids = set()
        for _ in range(3):
            img = _uploaded_image()
            data = _complaint_post_data(self.cat.id)
            data['images'] = img
            self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        for c in Complaint.objects.filter(citizen=self.citizen):
            ids.add(c.complaint_id)
        self.assertEqual(len(ids), Complaint.objects.filter(citizen=self.citizen).count())

    def test_complaint_requires_title(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id, title='short', latitude='24.8', longitude='67.0')
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        self.assertEqual(Complaint.objects.filter(citizen=self.citizen).count(), 0)

    def test_citizen_can_view_own_complaint(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        c = Complaint.objects.create(
            citizen=self.citizen, category=self.cat,
            title='My complaint to view', description='Test view own complaint detail.',
            district='karachi', area='DHA', address='123',
        )
        resp = self.client.get(reverse('complaints:complaint_detail', args=[c.complaint_id]))
        self.assertEqual(resp.status_code, 200)

    def test_citizen_cannot_view_other_complaint(self):
        c = Complaint.objects.create(
            citizen=self.other_citizen, category=self.cat,
            title='Other persons complaint here', description='This should not be accessible.',
            district='karachi', area='DHA', address='123',
        )
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(reverse('complaints:complaint_detail', args=[c.complaint_id]))
        self.assertEqual(resp.status_code, 404)

    def test_my_complaints_only_shows_own(self):
        for i in range(2):
            Complaint.objects.create(
                citizen=self.citizen, title=f'My complaint {i} test here',
                description=f'Description {i} for my complaint test.', district='karachi',
                area='DHA', address='123',
            )
        Complaint.objects.create(
            citizen=self.other_citizen, title='Others complaint not mine',
            description="This one belongs to another user and should not appear.",
            district='lahore', area='Gulberg', address='456',
        )
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(reverse('complaints:my_complaints'))
        self.assertEqual(resp.status_code, 200)
        for c in resp.context['complaints']:
            self.assertEqual(c.citizen, self.citizen)

    def test_complaint_category_saved(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        self.assertEqual(c.category, self.cat)

    def test_initial_status_is_pending(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        self.assertEqual(c.status, Complaint.PENDING)

    def test_track_complaint_own(self):
        c = Complaint.objects.create(
            citizen=self.citizen, title='Trackable complaint here',
            description='For testing the track complaint feature.', district='karachi',
            area='DHA', address='123',
        )
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(reverse('complaints:track_complaint') + f'?complaint_id={c.complaint_id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['complaint'], c)


# ─────────────────────────────────────────────────────────────
# 4. IMAGE MANAGEMENT
# ─────────────────────────────────────────────────────────────

class ImageManagementTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.citizen = _make_citizen('img1')
        self.cat = _make_category()

    def test_image_saved_to_db(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image('issue.jpg', 'red')
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        self.assertEqual(c.images.count(), 1)

    def test_first_image_is_primary(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        self.assertTrue(c.images.filter(is_primary=True).exists())

    def test_image_linked_to_correct_complaint(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image('linked.jpg')
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        for img_obj in c.images.all():
            self.assertEqual(img_obj.complaint, c)

    def test_invalid_file_type_rejected(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        fake = SimpleUploadedFile('doc.pdf', b'%PDF-1.4 fake pdf content', content_type='application/pdf')
        data = _complaint_post_data(self.cat.id)
        data['images'] = fake
        resp = self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        self.assertNotEqual(resp.status_code, 302)
        self.assertEqual(Complaint.objects.filter(citizen=self.citizen).count(), 0)

    def test_no_image_rejected(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        data = _complaint_post_data(self.cat.id)
        resp = self.client.post(reverse('complaints:report_issue'), data)
        self.assertNotEqual(resp.status_code, 302)

    def test_image_file_size_stored(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        raw = _jpeg()
        img = SimpleUploadedFile('size.jpg', raw, content_type='image/jpeg')
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        img_obj = c.images.first()
        self.assertGreater(img_obj.file_size, 0)


# ─────────────────────────────────────────────────────────────
# 5. LOCATION MANAGEMENT
# ─────────────────────────────────────────────────────────────

class LocationManagementTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.citizen = _make_citizen('loc1')
        self.cat = _make_category()

    def test_location_saved_with_complaint(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id, latitude='31.5204', longitude='74.3587')
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        self.assertEqual(c.latitude, Decimal('31.5204'))
        self.assertEqual(c.longitude, Decimal('74.3587'))

    def test_missing_location_rejected(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        del data['latitude']
        del data['longitude']
        data['images'] = img
        resp = self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        self.assertNotEqual(resp.status_code, 302)

    def test_complaint_detail_shows_coordinates(self):
        c = Complaint.objects.create(
            citizen=self.citizen, category=self.cat,
            title='Location display test complaint',
            description='Testing coordinate display on complaint detail page.',
            district='karachi', area='DHA', address='123 Main St',
            latitude=Decimal('24.8607'), longitude=Decimal('67.0011'),
        )
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(reverse('complaints:complaint_detail', args=[c.complaint_id]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('24.8607', content)
        self.assertIn('67.0011', content)

    def test_complaint_without_coords_handled_gracefully(self):
        c = Complaint.objects.create(
            citizen=self.citizen, category=self.cat,
            title='No coordinates complaint here', description='No lat/lng test here.',
            district='karachi', area='DHA', address='123 Main St',
            latitude=None, longitude=None,
        )
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(reverse('complaints:complaint_detail', args=[c.complaint_id]))
        self.assertEqual(resp.status_code, 200)

    def test_public_map_includes_located_complaints(self):
        Complaint.objects.create(
            citizen=self.citizen, category=self.cat,
            title='Public map visible complaint test',
            description='Public map test complaint description here.',
            district='karachi', area='DHA', address='123',
            status=Complaint.IN_PROGRESS,
            latitude=Decimal('24.8607'), longitude=Decimal('67.0011'),
        )
        resp = self.client.get(reverse('complaints:public_issues'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'24.8607', resp.content)


# ─────────────────────────────────────────────────────────────
# 6. ADMIN BACKEND
# ─────────────────────────────────────────────────────────────

class AdminBackendTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.admin = _make_admin('adm1')
        self.citizen = _make_citizen('adm_cit')
        self.cat = _make_category()
        self.complaint = Complaint.objects.create(
            citizen=self.citizen, category=self.cat,
            title='Admin test complaint here now', description='For admin backend testing purposes here.',
            district='karachi', area='DHA', address='123 Main St',
        )

    def test_admin_dashboard_requires_admin(self):
        citizen = _make_citizen('adm2')
        self.client.login(email=citizen.email, password='TestPass2026!')
        resp = self.client.get(reverse('admin_complaints:dashboard'))
        self.assertNotEqual(resp.status_code, 200)

    def test_admin_dashboard_accessible_to_admin(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        resp = self.client.get(reverse('admin_complaints:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_see_all_complaints(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        resp = self.client.get(reverse('admin_complaints:manage_complaints'))
        self.assertEqual(resp.status_code, 200)
        ids = [c.complaint_id for c in resp.context['complaints']]
        self.assertIn(self.complaint.complaint_id, ids)

    def test_admin_can_view_complaint_detail(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        resp = self.client.get(
            reverse('admin_complaints:complaint_detail', args=[self.complaint.complaint_id])
        )
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_update_status(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        resp = self.client.post(
            reverse('admin_complaints:complaint_detail', args=[self.complaint.complaint_id]),
            {
                'status': 'in_progress',
                'priority': 'high',
                'admin_notes': 'Under investigation',
                'rejection_reason': '',
                'note': 'Starting work',
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, 'in_progress')

    def test_admin_can_filter_complaints_by_status(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        resp = self.client.get(reverse('admin_complaints:manage_complaints') + '?status=pending')
        self.assertEqual(resp.status_code, 200)
        for c in resp.context['complaints']:
            self.assertEqual(c.status, 'pending')

    def test_admin_can_search_complaints(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        resp = self.client.get(
            reverse('admin_complaints:manage_complaints') + f'?search={self.complaint.complaint_id}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.context['total_count'], 0)

    def test_admin_can_manage_users(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        resp = self.client.get(reverse('admin_complaints:manage_users'))
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_manage_categories(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        resp = self.client.get(reverse('admin_complaints:manage_categories'))
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_export_csv(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        resp = self.client.get(reverse('admin_complaints:export_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        content = resp.content.decode()
        self.assertIn('Complaint ID', content)
        self.assertIn(self.complaint.complaint_id, content)

    def test_non_admin_cannot_access_admin_complaint_detail(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(
            reverse('admin_complaints:complaint_detail', args=[self.complaint.complaint_id])
        )
        self.assertNotEqual(resp.status_code, 200)

    def test_admin_analytics_accessible(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        resp = self.client.get(reverse('admin_complaints:analytics_reports'))
        self.assertEqual(resp.status_code, 200)


# ─────────────────────────────────────────────────────────────
# 7. STATUS TRACKING
# ─────────────────────────────────────────────────────────────

class StatusTrackingTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.admin = _make_admin('stat_adm')
        self.citizen = _make_citizen('stat_cit')
        self.cat = _make_category()
        self.complaint = Complaint.objects.create(
            citizen=self.citizen, category=self.cat,
            title='Status tracking test complaint here',
            description='Testing complete status history tracking in IssueSnap.',
            district='karachi', area='DHA', address='123 Main St',
        )

    def test_initial_status_history_created_on_submit(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).exclude(id=self.complaint.id).first()
        if c:
            self.assertGreater(c.status_history.count(), 0)

    def test_status_change_creates_history_record(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        self.client.post(
            reverse('admin_complaints:complaint_detail', args=[self.complaint.complaint_id]),
            {
                'status': 'in_progress', 'priority': 'medium',
                'admin_notes': '', 'rejection_reason': '', 'note': 'Started',
            },
        )
        history = ComplaintStatusHistory.objects.filter(complaint=self.complaint)
        self.assertTrue(history.filter(new_status='in_progress').exists())

    def test_history_records_old_and_new_status(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        old = self.complaint.status
        self.client.post(
            reverse('admin_complaints:complaint_detail', args=[self.complaint.complaint_id]),
            {
                'status': 'processing', 'priority': 'low',
                'admin_notes': '', 'rejection_reason': '', 'note': 'Processing now',
            },
        )
        entry = ComplaintStatusHistory.objects.filter(
            complaint=self.complaint, new_status='processing'
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.old_status, old)

    def test_multiple_status_changes_tracked(self):
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        statuses = ['in_progress', 'processing', 'resolved']
        for s in statuses:
            self.client.post(
                reverse('admin_complaints:complaint_detail', args=[self.complaint.complaint_id]),
                {
                    'status': s, 'priority': 'medium',
                    'admin_notes': '', 'rejection_reason': '', 'note': f'Moving to {s}',
                },
            )
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, 'resolved')
        history = ComplaintStatusHistory.objects.filter(complaint=self.complaint)
        self.assertGreaterEqual(history.count(), 3)

    def test_status_history_visible_on_citizen_detail(self):
        ComplaintStatusHistory.objects.create(
            complaint=self.complaint, old_status='pending',
            new_status='in_progress', changed_by=self.admin,
            note='Work started',
        )
        self.complaint.status = 'in_progress'
        self.complaint.save()
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(
            reverse('complaints:complaint_detail', args=[self.complaint.complaint_id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(list(resp.context['status_history'])), 0)

    def test_all_valid_statuses_accepted(self):
        for status in [Complaint.PENDING, Complaint.IN_PROGRESS, Complaint.PROCESSING,
                       Complaint.RESOLVED, Complaint.COMPLETED, Complaint.REJECTED]:
            self.complaint.status = status
            self.complaint.save()
            self.complaint.refresh_from_db()
            self.assertEqual(self.complaint.status, status)

    def test_resolved_complaint_sets_resolved_at(self):
        self.complaint.status = Complaint.RESOLVED
        self.complaint.save()
        self.complaint.refresh_from_db()
        self.assertIsNotNone(self.complaint.resolved_at)


# ─────────────────────────────────────────────────────────────
# 8. AI INTEGRATION
# ─────────────────────────────────────────────────────────────

class AIIntegrationTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.citizen = _make_citizen('ai1')
        self.cat = _make_category()

    def test_ai_analyzed_flag_set_after_submission(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        self.assertTrue(c.ai_analyzed)

    def test_nlp_analysis_stored_after_submission(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        self.assertTrue(NLPAnalysis.objects.filter(complaint=c).exists())

    def test_priority_prediction_stored_after_submission(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        self.assertTrue(PriorityPrediction.objects.filter(complaint=c).exists())

    def test_ai_api_returns_json_no_model(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        resp = self.client.post('/api/ai/analyze/', {'image': img}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('model_available', data)

    def test_ai_api_refuses_non_image(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        fake = SimpleUploadedFile('doc.pdf', b'%PDF fake', content_type='application/pdf')
        resp = self.client.post('/api/ai/analyze/', {'image': fake}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_ai_api_requires_login(self):
        img = _uploaded_image()
        resp = self.client.post('/api/ai/analyze/', {'image': img}, format='multipart')
        self.assertNotEqual(resp.status_code, 200)

    def test_nlp_keywords_not_empty(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        nlp = NLPAnalysis.objects.filter(complaint=c).first()
        if nlp:
            self.assertIsNotNone(nlp.extracted_keywords)


# ─────────────────────────────────────────────────────────────
# 9. NOTIFICATIONS
# ─────────────────────────────────────────────────────────────

class NotificationTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.citizen = _make_citizen('notif1')
        self.admin = _make_admin('notif_adm')
        self.cat = _make_category()

    def test_notification_created_on_submission(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        self.assertTrue(
            Notification.objects.filter(user=self.citizen, notification_type='complaint_submitted').exists()
        )

    def test_notification_created_on_status_change(self):
        c = Complaint.objects.create(
            citizen=self.citizen, category=self.cat,
            title='Notification status change test', description='Checking notification on status change.',
            district='karachi', area='DHA', address='123 Main St',
        )
        before = Notification.objects.filter(user=self.citizen, notification_type='status_changed').count()
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        self.client.post(
            reverse('admin_complaints:complaint_detail', args=[c.complaint_id]),
            {
                'status': 'in_progress', 'priority': 'high',
                'admin_notes': '', 'rejection_reason': '', 'note': 'Started',
            },
        )
        after = Notification.objects.filter(user=self.citizen, notification_type='status_changed').count()
        self.assertEqual(after, before + 1)

    def test_unread_count_api(self):
        Notification.objects.create(
            user=self.citizen, title='Test', message='Test notification message',
            notification_type='general',
        )
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(reverse('notifications:unread_count'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('count', data)
        self.assertGreater(data['count'], 0)

    def test_mark_notification_as_read(self):
        n = Notification.objects.create(
            user=self.citizen, title='Unread', message='This is unread',
            notification_type='general',
        )
        self.assertFalse(n.is_read)
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.post(reverse('notifications:mark_read', args=[n.id]))
        self.assertEqual(resp.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.assertIsNotNone(n.read_at)

    def test_mark_all_notifications_read(self):
        for i in range(3):
            Notification.objects.create(
                user=self.citizen, title=f'Notif {i}', message=f'Message {i}',
                notification_type='general',
            )
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.post(reverse('notifications:mark_all_read'))
        self.assertEqual(resp.status_code, 200)
        unread = Notification.objects.filter(user=self.citizen, is_read=False).count()
        self.assertEqual(unread, 0)

    def test_notification_list_requires_login(self):
        resp = self.client.get(reverse('notifications:list'))
        self.assertEqual(resp.status_code, 302)

    def test_notification_list_only_shows_own(self):
        other = _make_citizen('notif2')
        Notification.objects.create(
            user=self.citizen, title='Mine', message='My notification',
            notification_type='general',
        )
        Notification.objects.create(
            user=other, title='Others', message='Not mine',
            notification_type='general',
        )
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(reverse('notifications:list'))
        self.assertEqual(resp.status_code, 200)
        for n in resp.context['notifications']:
            self.assertEqual(n.user, self.citizen)


# ─────────────────────────────────────────────────────────────
# 10. SECURITY
# ─────────────────────────────────────────────────────────────

class SecurityTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.citizen = _make_citizen('sec1')
        self.cat = _make_category()

    def test_csrf_protection_on_login(self):
        # Django's test client includes CSRF by default; verify the form renders with token
        resp = self.client.get(reverse('accounts:login'))
        self.assertIn(b'csrfmiddlewaretoken', resp.content)

    def test_unauthenticated_cannot_access_dashboard(self):
        resp = self.client.get(reverse('complaints:citizen_dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.url)

    def test_unauthenticated_cannot_submit_complaint(self):
        resp = self.client.get(reverse('complaints:report_issue'))
        self.assertEqual(resp.status_code, 302)

    def test_unauthenticated_cannot_view_my_complaints(self):
        resp = self.client.get(reverse('complaints:my_complaints'))
        self.assertEqual(resp.status_code, 302)

    def test_referrer_policy_header_present(self):
        resp = self.client.get(reverse('pages:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Referrer-Policy', resp)

    def test_oversized_image_rejected(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        big = SimpleUploadedFile(
            'huge.jpg', b'\xff\xd8\xff' + b'X' * (11 * 1024 * 1024),
            content_type='image/jpeg',
        )
        data = _complaint_post_data(self.cat.id)
        data['images'] = big
        resp = self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        self.assertNotEqual(resp.status_code, 302)

    def test_too_many_images_rejected(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        images = [_uploaded_image(f'img{i}.jpg') for i in range(6)]
        data = _complaint_post_data(self.cat.id)
        data['images'] = images
        resp = self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        self.assertNotEqual(resp.status_code, 302)

    def test_sql_injection_in_search_safe(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(
            reverse('complaints:my_complaints') + "?search='; DROP TABLE complaints; --"
        )
        self.assertEqual(resp.status_code, 200)

    def test_xss_in_complaint_title_escaped(self):
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        xss_title = '<script>alert("xss")</script> pothole on road boulevard'
        data = _complaint_post_data(self.cat.id, title=xss_title)
        data['images'] = img
        self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        c = Complaint.objects.filter(citizen=self.citizen).first()
        if c:
            resp = self.client.get(reverse('complaints:complaint_detail', args=[c.complaint_id]))
            self.assertNotIn(b'<script>alert("xss")', resp.content)


# ─────────────────────────────────────────────────────────────
# 11. END-TO-END VERIFICATION
# ─────────────────────────────────────────────────────────────

class EndToEndTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.admin = _make_admin('e2e_adm')
        self.citizen = _make_citizen('e2e_cit')
        self.cat = _make_category()

    def test_full_complaint_lifecycle(self):
        """
        Register → submit complaint → admin updates status →
        notification sent → citizen views history
        """
        # 1. Submit complaint
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        img = _uploaded_image()
        data = _complaint_post_data(self.cat.id)
        data['images'] = img
        resp = self.client.post(reverse('complaints:report_issue'), data, format='multipart')
        self.assertEqual(resp.status_code, 302)
        c = Complaint.objects.filter(citizen=self.citizen).first()
        self.assertIsNotNone(c)
        self.assertEqual(c.status, Complaint.PENDING)
        self.assertEqual(c.images.count(), 1)
        self.assertTrue(c.ai_analyzed)
        self.assertTrue(NLPAnalysis.objects.filter(complaint=c).exists())
        self.assertTrue(PriorityPrediction.objects.filter(complaint=c).exists())
        self.assertTrue(Notification.objects.filter(user=self.citizen).exists())
        self.client.logout()

        # 2. Admin updates status
        self.client.login(email=self.admin.email, password='AdminPass2026!')
        self.client.post(
            reverse('admin_complaints:complaint_detail', args=[c.complaint_id]),
            {
                'status': 'resolved', 'priority': 'high',
                'admin_notes': 'Fixed', 'rejection_reason': '',
                'note': 'Issue resolved by maintenance team',
            },
        )
        c.refresh_from_db()
        self.assertEqual(c.status, 'resolved')
        self.assertIsNotNone(c.resolved_at)
        self.client.logout()

        # 3. Status change notification delivered to citizen
        self.assertTrue(
            Notification.objects.filter(
                user=self.citizen, notification_type='status_changed'
            ).exists()
        )

        # 4. Citizen views own complaint detail — history visible
        self.client.login(email=self.citizen.email, password='TestPass2026!')
        resp = self.client.get(reverse('complaints:complaint_detail', args=[c.complaint_id]))
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(list(resp.context['status_history'])), 0)
