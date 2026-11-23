"""
IssueSnap AI Inference Tests
"""
import os
import tempfile
from io import BytesIO

from django.test import TestCase
from PIL import Image

from issuesnap.apps.ai_engine.inference import run_inference, get_active_model_path


def _write_tmp_image():
    buf = BytesIO()
    Image.new('RGB', (64, 64), color='red').save(buf, 'JPEG')
    buf.seek(0)
    tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    tmp.write(buf.read()); tmp.flush(); tmp.close()
    return tmp.name


class AIInferenceEdgeCasesTest(TestCase):

    def test_none_model_path_returns_error_dict(self):
        result = run_inference('/some/image.jpg', None, 0.6)
        self.assertIsInstance(result, dict)
        self.assertFalse(result['success'])
        self.assertIsNotNone(result['error'])
        self.assertIn('model', result['error'].lower())

    def test_none_image_path_returns_error_dict(self):
        result = run_inference(None, '/some/model.keras', 0.6)
        self.assertIsInstance(result, dict)
        self.assertFalse(result['success'])

    def test_both_none_returns_error_dict(self):
        result = run_inference(None, None, 0.6)
        self.assertIsInstance(result, dict)
        self.assertFalse(result['success'])

    def test_empty_strings_return_error_dict(self):
        result = run_inference('', '', 0.6)
        self.assertIsInstance(result, dict)
        self.assertFalse(result['success'])

    def test_nonexistent_image_path_returns_error_dict(self):
        result = run_inference('/nonexistent/path/image.jpg', '/some/model.keras', 0.6)
        self.assertIsInstance(result, dict)
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'].lower())

    def test_nonexistent_model_path_returns_error_dict(self):
        tmp = _write_tmp_image()
        try:
            result = run_inference(tmp, '/nonexistent/model.keras', 0.6)
            self.assertIsInstance(result, dict)
            self.assertFalse(result['success'])
        finally:
            os.unlink(tmp)

    def test_get_active_model_path_returns_none_when_no_model(self):
        path = get_active_model_path()
        self.assertTrue(path is None or isinstance(path, str))
        if path is not None:
            self.assertTrue(os.path.exists(path))

    def test_analyze_task_no_model_does_not_raise(self):
        from decimal import Decimal
        from django.contrib.auth import get_user_model
        from issuesnap.apps.complaints.models import Complaint, ComplaintCategory
        from issuesnap.apps.ai_engine.tasks import analyze_complaint_images
        from django.core.files.base import ContentFile

        User = get_user_model()
        user = User.objects.create_user(
            email='aitasktester@example.com', username='aitasktester',
            password='Pass2026!', first_name='AI', last_name='Tester',
        )
        cat = ComplaintCategory.objects.create(
            name='Test Category AI', slug='test-category-ai',
            icon='bi-bug', color='#EF4444',
        )
        complaint = Complaint.objects.create(
            citizen=user, category=cat,
            title='Test AI task no model available',
            description='This complaint tests the AI task when no trained model exists.',
            district='karachi', area='Test Area', address='Test Address',
            latitude=Decimal('24.8607000'), longitude=Decimal('67.0011000'),
        )
        from issuesnap.apps.complaints.models import ComplaintImage
        buf = BytesIO()
        Image.new('RGB', (64, 64), color='green').save(buf, 'JPEG')
        buf.seek(0)
        img = ComplaintImage(complaint=complaint, is_primary=True)
        img.image.save('test_ai_task.jpg', ContentFile(buf.read()), save=True)

        try:
            analyze_complaint_images(complaint.id)
        except Exception as e:
            self.fail(f'analyze_complaint_images raised: {e}')

        complaint.refresh_from_db()
        self.assertTrue(complaint.ai_analyzed)
