"""Test the AI analyze API endpoint."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'issuesnap.config.settings')
import django; django.setup()
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image

c = Client(HTTP_HOST='127.0.0.1')
c.login(email='citizen@issuesnap.com', password='CitizenPass2026!')
buf = BytesIO()
Image.new('RGB', (224, 224), color='gray').save(buf, 'JPEG')
buf.seek(0)
img = SimpleUploadedFile('test.jpg', buf.read(), 'image/jpeg')
resp = c.post('/api/ai/analyze/', {'image': img}, format='multipart')
print('AI API status:', resp.status_code)
try:
    data = resp.json()
    print('  model_available:', data.get('model_available'))
    print('  success:', data.get('success'))
    print('  message:', str(data.get('message', ''))[:120])
    print('  error:', str(data.get('error', ''))[:120])
except Exception as e:
    print('  JSON parse error:', e)

# Also test admin complaint detail view
admin_c = Client(HTTP_HOST='127.0.0.1')
admin_c.login(email='admin@issuesnap.com', password='AdminPass2026!')
from issuesnap.apps.complaints.models import Complaint
comp = Complaint.objects.first()
resp2 = admin_c.get(f'/admin-panel/complaints/{comp.complaint_id}/')
print('\nAdmin complaint detail:', resp2.status_code)
print('  Has AI results section:', b'AI Classifications' in resp2.content or b'AI Analysis' in resp2.content)
print('  Has priority prediction:', b'Priority Prediction' in resp2.content)
print('  Has status update form:', b'Update Status' in resp2.content)
