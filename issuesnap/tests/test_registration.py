"""
IssueSnap Registration Tests
Verifies that exactly one UserProfile is created per registered user,
and that the IntegrityError on duplicate profile creation is fixed.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from issuesnap.apps.accounts.models import UserProfile

User = get_user_model()


class RegistrationProfileTest(TestCase):
    """Tests for the registration → UserProfile creation flow."""

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.register_url = reverse('accounts:register')

    def _register_data(self, suffix=''):
        return {
            'first_name': 'Test',
            'last_name': 'User' + suffix,
            'email': f'testuser{suffix}@example.com',
            'username': f'testuser{suffix}',
            'password': 'StrongPass2026!',
            'confirm_password': 'StrongPass2026!',
            'agree_terms': 'on',
        }

    def test_registration_creates_exactly_one_profile(self):
        data = self._register_data('1')
        response = self.client.post(self.register_url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email='testuser1@example.com').exists())
        user = User.objects.get(email='testuser1@example.com')
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)

    def test_multiple_registrations_each_get_one_profile(self):
        for i in range(2, 6):
            data = self._register_data(str(i))
            response = self.client.post(self.register_url, data, follow=True)
            self.assertEqual(response.status_code, 200)
            self.client.logout()

        for i in range(2, 6):
            email = f'testuser{i}@example.com'
            self.assertTrue(User.objects.filter(email=email).exists())
            user = User.objects.get(email=email)
            self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)

    def test_duplicate_email_rejected_gracefully(self):
        data = self._register_data('dup')
        self.client.post(self.register_url, data, follow=True)
        before = User.objects.filter(email='testuserdup@example.com').count()
        response = self.client.post(self.register_url, data, follow=True)
        after = User.objects.filter(email='testuserdup@example.com').count()
        self.assertEqual(before, after)
        self.assertEqual(response.status_code, 200)

    def test_duplicate_username_rejected_gracefully(self):
        data = self._register_data('dupun')
        self.client.post(self.register_url, data, follow=True)
        data2 = self._register_data('dupun2')
        data2['username'] = 'testuserdupun'
        before = User.objects.filter(username='testuserdupun').count()
        response = self.client.post(self.register_url, data2, follow=True)
        after = User.objects.filter(username='testuserdupun').count()
        self.assertEqual(before, after)
        self.assertEqual(response.status_code, 200)

    def test_existing_user_with_profile_no_error(self):
        user = User.objects.create_user(
            email='existing@example.com', username='existing',
            password='ExistingPass2026!', first_name='Existing', last_name='User',
        )
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)
        self.client.login(email='existing@example.com', password='ExistingPass2026!')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)

    def test_password_mismatch_rejected(self):
        data = self._register_data('mismatch')
        data['confirm_password'] = 'DifferentPassword2026!'
        before = User.objects.filter(email='testusermismatch@example.com').count()
        self.client.post(self.register_url, data, follow=True)
        after = User.objects.filter(email='testusermismatch@example.com').count()
        self.assertEqual(before, after)

    def test_no_terms_agreement_rejected(self):
        data = self._register_data('noterms')
        data['agree_terms'] = ''
        before = User.objects.filter(email='testusernoterms@example.com').count()
        self.client.post(self.register_url, data, follow=True)
        after = User.objects.filter(email='testusernoterms@example.com').count()
        self.assertEqual(before, after)

    def test_registered_user_has_citizen_role(self):
        data = self._register_data('role')
        self.client.post(self.register_url, data, follow=True)
        user = User.objects.get(email='testuserrole@example.com')
        self.assertEqual(user.role, User.CITIZEN)
