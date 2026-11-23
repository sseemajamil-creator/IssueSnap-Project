"""
IssueSnap Map Feature Tests
Verifies the complete workflow: select location → save complaint → view location → admin map.
"""
from io import BytesIO
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from issuesnap.apps.accounts.models import User, UserProfile
from issuesnap.apps.complaints.models import Complaint, ComplaintImage


def _make_image(color='blue'):
    buf = BytesIO()
    Image.new('RGB', (100, 100), color=color).save(buf, 'JPEG')
    buf.seek(0)
    return buf


class MapFeatureTest(TestCase):

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.citizen = User.objects.create_user(
            email='mapcitizen@example.com', username='mapcitizen',
            password='CitizenPass2026!', first_name='Map', last_name='Tester',
        )
        self.admin = User.objects.create_user(
            email='mapadmin@example.com', username='mapadmin',
            password='AdminPass2026!', first_name='Map', last_name='Admin',
        )
        self.admin.role = User.ADMIN
        self.admin.is_staff = True
        self.admin.save()

        from issuesnap.apps.complaints.models import ComplaintCategory
        if not ComplaintCategory.objects.exists():
            ComplaintCategory.objects.create(
                name='Road Pothole', slug='pothole',
                icon='bi-exclamation-triangle', color='#EF4444',
                is_ai_supported=True, ai_class_name='pothole',
            )

    def test_complaint_without_location_rejected(self):
        self.client.login(email='mapcitizen@example.com', password='CitizenPass2026!')
        img = SimpleUploadedFile('test.jpg', _make_image().read(), 'image/jpeg')
        response = self.client.post(reverse('complaints:report_issue'), {
            'title': 'Large pothole on Main Boulevard causing accidents',
            'description': 'A dangerous pothole that needs urgent repair before more accidents.',
            'category': '1', 'district': 'karachi', 'area': 'DHA Phase 5',
            'address': 'House 12, Street 3, DHA Phase 5', 'landmark': 'Near hospital',
            'images': img,
        }, format='multipart')
        self.assertNotEqual(response.status_code, 302)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_complaint_with_location_saved(self):
        self.client.login(email='mapcitizen@example.com', password='CitizenPass2026!')
        img = SimpleUploadedFile('test.jpg', _make_image().read(), 'image/jpeg')
        response = self.client.post(reverse('complaints:report_issue'), {
            'title': 'Large pothole on Main Boulevard causing accidents',
            'description': 'A dangerous pothole that needs urgent repair before more accidents.',
            'category': '1', 'district': 'karachi', 'area': 'DHA Phase 5',
            'address': 'House 12, Street 3, DHA Phase 5', 'landmark': 'Near hospital',
            'latitude': '24.8607000', 'longitude': '67.0011000', 'images': img,
        }, format='multipart')
        self.assertEqual(response.status_code, 302)
        complaint = Complaint.objects.first()
        self.assertIsNotNone(complaint)
        self.assertEqual(complaint.latitude, Decimal('24.8607000'))
        self.assertEqual(complaint.longitude, Decimal('67.0011000'))
        self.assertTrue(complaint.ai_analyzed)

    def test_complaint_detail_shows_map(self):
        self.client.login(email='mapcitizen@example.com', password='CitizenPass2026!')
        complaint = Complaint.objects.create(
            citizen=self.citizen,
            title='Test pothole issue for map display',
            description='Testing map display on complaint detail page with real coordinates.',
            district='karachi', area='DHA Phase 5', address='House 12, Street 3',
            latitude=Decimal('24.8607000'), longitude=Decimal('67.0011000'),
        )
        response = self.client.get(reverse('complaints:complaint_detail', args=[complaint.complaint_id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'complaint-map', response.content)
        self.assertIn(b'24.8607', response.content)

    def test_report_page_has_map(self):
        self.client.login(email='mapcitizen@example.com', password='CitizenPass2026!')
        response = self.client.get(reverse('complaints:report_issue'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'location-map', response.content)
        self.assertIn(b'btn-use-location', response.content)
        self.assertIn(b'btn-clear-location', response.content)
        self.assertIn(b'id_latitude', response.content)

    def test_admin_dashboard_has_map(self):
        Complaint.objects.create(
            citizen=self.citizen,
            title='Admin map test complaint for pothole',
            description='Testing that admin dashboard map shows complaint markers.',
            district='karachi', area='DHA Phase 5', address='House 12, Street 3',
            latitude=Decimal('24.8607000'), longitude=Decimal('67.0011000'),
        )
        self.client.login(email='mapadmin@example.com', password='AdminPass2026!')
        response = self.client.get(reverse('admin_complaints:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'admin-complaint-map', response.content)
        self.assertIn(b'24.8607', response.content)

    def test_admin_dashboard_map_empty(self):
        self.client.login(email='mapadmin@example.com', password='AdminPass2026!')
        response = self.client.get(reverse('admin_complaints:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'admin-complaint-map', response.content)

    def test_admin_map_multiple_complaints(self):
        for i in range(3):
            Complaint.objects.create(
                citizen=self.citizen,
                title=f'Test complaint {i} for map display purposes',
                description=f'Description for complaint {i} with enough characters here.',
                district='karachi', area=f'Area {i}', address=f'Address {i}',
                latitude=Decimal(f'24.86{i:01d}000'),
                longitude=Decimal(f'67.00{i:01d}000'),
            )
        self.client.login(email='mapadmin@example.com', password='AdminPass2026!')
        response = self.client.get(reverse('admin_complaints:dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('24.8600', content)
        self.assertIn('24.8610', content)

    def test_detail_page_no_coordinates(self):
        complaint = Complaint.objects.create(
            citizen=self.citizen,
            title='Complaint without coordinates for testing edge case',
            description='This complaint has no latitude or longitude set on purpose.',
            district='karachi', area='DHA', address='Some address',
            latitude=None, longitude=None,
        )
        self.client.login(email='mapcitizen@example.com', password='CitizenPass2026!')
        response = self.client.get(reverse('complaints:complaint_detail', args=[complaint.complaint_id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'No map coordinates', response.content)

    def test_registration_still_works(self):
        response = self.client.post(reverse('accounts:register'), {
            'first_name': 'New', 'last_name': 'Mapper',
            'email': 'newmapper@example.com', 'username': 'newmapper',
            'password': 'StrongPass2026!', 'confirm_password': 'StrongPass2026!',
            'agree_terms': 'on',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email='newmapper@example.com')
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)

    def test_public_issues_page(self):
        response = self.client.get(reverse('complaints:public_issues'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'hotspot-map', response.content)
