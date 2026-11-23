"""
IssueSnap AI Engine API Views
"""
import os
import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .inference import run_inference, get_active_model_path, CIVIC_CLASSES, CLASS_DISPLAY_NAMES
from .models import ModelVersion

logger = logging.getLogger(__name__)


@login_required
@require_POST
def analyze_image_api(request):
    """
    API endpoint: analyze a single uploaded image.
    Returns JSON with prediction results.
    """
    if 'image' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No image provided.'}, status=400)

    image_file = request.FILES['image']

    # Validate
    allowed_types = ['image/jpeg', 'image/png', 'image/webp']
    if image_file.content_type not in allowed_types:
        return JsonResponse({'success': False, 'error': 'Invalid image type.'}, status=400)

    if image_file.size > 10 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': 'Image too large (max 10MB).'}, status=400)

    # Save temporarily
    import tempfile, os as _os
    _temp_dir = settings.MEDIA_ROOT / 'temp'
    _os.makedirs(_temp_dir, exist_ok=True)
    suffix = os.path.splitext(image_file.name)[1] or '.jpg'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=str(_temp_dir)) as tmp:
        for chunk in image_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        model_path = get_active_model_path()
        threshold = settings.AI_CONFIDENCE_THRESHOLD

        if model_path is None:
            return JsonResponse({
                'success': False,
                'model_available': False,
                'error': 'No trained model is currently available. AI analysis will be performed after model training.',
                'message': 'Your complaint will still be submitted. Manual review will be performed.',
            })

        result = run_inference(tmp_path, model_path, threshold)
        result['model_available'] = True
        return JsonResponse(result)

    except Exception as e:
        logger.error(f'API inference error: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@login_required
def model_info_api(request):
    """Return info about the active model."""
    model_version = ModelVersion.objects.filter(is_active=True, is_trained=True).first()
    model_path = get_active_model_path()

    return JsonResponse({
        'model_available': model_path is not None,
        'model_trained': model_version is not None,
        'model_name': model_version.name if model_version else None,
        'model_version': model_version.version if model_version else None,
        'accuracy': model_version.accuracy if model_version else None,
        'supported_classes': [
            {'class': c, 'display_name': CLASS_DISPLAY_NAMES[c]}
            for c in CIVIC_CLASSES
        ],
    })


@login_required
def supported_classes_api(request):
    """Return list of supported AI classes."""
    return JsonResponse({
        'classes': [
            {'class': c, 'display_name': CLASS_DISPLAY_NAMES[c]}
            for c in CIVIC_CLASSES
        ]
    })
