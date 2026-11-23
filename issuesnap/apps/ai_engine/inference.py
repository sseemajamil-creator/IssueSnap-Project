"""
IssueSnap AI Inference Engine
Real model inference using TensorFlow/Keras
"""
import os
import time
import logging
import numpy as np
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

# Class labels matching the trained model
CIVIC_CLASSES = [
    'pothole',
    'road_crack',
    'garbage',
    'water_leakage',
    'drainage_blockage',
    'broken_streetlight',
    'damaged_infrastructure',
]

CLASS_DISPLAY_NAMES = {
    'pothole': 'Road Pothole',
    'road_crack': 'Road Crack',
    'garbage': 'Garbage Overflow',
    'water_leakage': 'Water Leakage',
    'drainage_blockage': 'Drainage Blockage',
    'broken_streetlight': 'Broken Streetlight',
    'damaged_infrastructure': 'Damaged Infrastructure',
}

_model_cache = {}


def get_model(model_path: str):
    """Load and cache a model. Supports both Keras (.keras) and scikit-learn (.pkl) models."""
    if model_path in _model_cache:
        return _model_cache[model_path]

    # ── scikit-learn model (.pkl) ──
    if model_path.endswith('.pkl'):
        try:
            import joblib
            model_package = joblib.load(model_path)
            _model_cache[model_path] = model_package
            logger.info(f'sklearn model loaded from {model_path}')
            return model_package
        except Exception as e:
            logger.error(f'Failed to load sklearn model from {model_path}: {e}')
            return None

    # ── Keras model (.keras) ──
    try:
        import tensorflow as tf
        model = tf.keras.models.load_model(model_path)
        _model_cache[model_path] = model
        logger.info(f'Keras model loaded from {model_path}')
        return model
    except Exception as e:
        logger.error(f'Failed to load model from {model_path}: {e}')
        return None


def preprocess_image(image_path: str, target_size=(224, 224)):
    """
    Preprocess an image for inference.
    Uses OpenCV for loading and preprocessing.
    Returns preprocessed numpy array.
    """
    try:
        import cv2
        img = cv2.imread(str(image_path))
        if img is None:
            logger.error(f'OpenCV could not read image: {image_path}')
            return None

        # Convert BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Resize
        img = cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)

        # Normalize to [0, 1]
        img = img.astype(np.float32) / 255.0

        # Add batch dimension
        img = np.expand_dims(img, axis=0)

        return img

    except Exception as e:
        logger.error(f'Image preprocessing failed for {image_path}: {e}')
        return None


def _run_sklearn_inference(model_package, image_path, threshold, result):
    """Run inference using a scikit-learn model package."""
    try:
        from issuesnap.ai.training.extract_features import extract_features as extract_feat
    except ImportError:
        # Fallback for when ai module is not on path
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from ai.training.extract_features import extract_features as extract_feat

    try:
        t_start = time.time()
        features = extract_feat(image_path)
        t_extract = time.time()

        if features is None:
            result['error'] = 'Feature extraction failed — image could not be processed.'
            return result

        classifier = model_package['classifier']
        categories = model_package.get('categories', CIVIC_CLASSES)
        display_names = model_package.get('class_display_names', CLASS_DISPLAY_NAMES)

        # Predict
        features_2d = features.reshape(1, -1)
        prediction = classifier.predict(features_2d)[0]
        probabilities = classifier.predict_proba(features_2d)[0]

        t_end = time.time()
        inference_time_ms = (t_end - t_start) * 1000.0

        predicted_idx = int(prediction)
        confidence = float(probabilities[predicted_idx])
        predicted_class = categories[predicted_idx] if predicted_idx < len(categories) else 'unknown'

        # Top 3 predictions
        top_indices = np.argsort(probabilities)[::-1][:3]
        top_predictions = [
            {
                'class': categories[int(i)] if int(i) < len(categories) else 'unknown',
                'display_name': display_names.get(
                    categories[int(i)] if int(i) < len(categories) else 'unknown',
                    'Unknown'
                ),
                'confidence': round(float(probabilities[i]), 4),
            }
            for i in top_indices
        ]

        all_probabilities = {
            categories[i]: round(float(probabilities[i]), 4)
            for i in range(min(len(categories), len(probabilities)))
        }

        result.update({
            'success': True,
            'predicted_class': predicted_class,
            'display_name': display_names.get(predicted_class, predicted_class),
            'confidence': round(confidence, 4),
            'top_predictions': top_predictions,
            'all_probabilities': all_probabilities,
            'is_above_threshold': confidence >= threshold,
            'inference_time_ms': round(inference_time_ms, 2),
        })

        logger.info(
            f'sklearn inference: {predicted_class} ({confidence:.2%}) in {inference_time_ms:.1f}ms'
        )
        return result

    except Exception as e:
        result['error'] = f'sklearn inference error: {str(e)}'
        logger.error(result['error'])
        return result


def run_inference(image_path: str, model_path: str, threshold: float = 0.60):
    """
    Run model inference on a single image.

    Returns:
        dict with keys:
            success: bool
            predicted_class: str
            confidence: float
            top_predictions: list of {class, confidence}
            all_probabilities: dict
            is_above_threshold: bool
            inference_time_ms: float
            error: str (only if success=False)
    """
    result = {
        'success': False,
        'predicted_class': None,
        'confidence': 0.0,
        'top_predictions': [],
        'all_probabilities': {},
        'is_above_threshold': False,
        'inference_time_ms': 0.0,
        'error': None,
    }

    # Validate inputs before calling os.path.exists (which raises TypeError on None).
    if not image_path:
        result['error'] = 'image_path is None or empty — cannot run inference.'
        logger.error(result['error'])
        return result

    if not model_path:
        result['error'] = 'No trained model is available. Train a model and place it in AI_MODEL_DIR.'
        logger.warning(result['error'])
        return result

    if not os.path.exists(image_path):
        result['error'] = f'Image file not found: {image_path}'
        logger.error(result['error'])
        return result

    if not os.path.exists(model_path):
        result['error'] = f'Model file not found: {model_path}'
        logger.warning(result['error'])
        return result

    model = get_model(model_path)
    if model is None:
        result['error'] = 'Failed to load model.'
        return result

    # ── scikit-learn model path ──
    if isinstance(model, dict) and 'classifier' in model:
        return _run_sklearn_inference(model, image_path, threshold, result)

    # ── Keras model path (original) ──
    img_array = preprocess_image(image_path)
    if img_array is None:
        result['error'] = 'Image preprocessing failed.'
        return result

    try:
        t_start = time.time()
        predictions = model.predict(img_array, verbose=0)
        t_end = time.time()

        inference_time_ms = (t_end - t_start) * 1000.0
        probs = predictions[0]

        predicted_idx = int(np.argmax(probs))
        confidence = float(probs[predicted_idx])
        predicted_class = CIVIC_CLASSES[predicted_idx] if predicted_idx < len(CIVIC_CLASSES) else 'unknown'

        # Top 3 predictions
        top_indices = np.argsort(probs)[::-1][:3]
        top_predictions = [
            {
                'class': CIVIC_CLASSES[int(i)] if int(i) < len(CIVIC_CLASSES) else 'unknown',
                'display_name': CLASS_DISPLAY_NAMES.get(
                    CIVIC_CLASSES[int(i)] if int(i) < len(CIVIC_CLASSES) else 'unknown',
                    'Unknown'
                ),
                'confidence': round(float(probs[i]), 4),
            }
            for i in top_indices
        ]

        all_probabilities = {
            CIVIC_CLASSES[i]: round(float(probs[i]), 4)
            for i in range(min(len(CIVIC_CLASSES), len(probs)))
        }

        result.update({
            'success': True,
            'predicted_class': predicted_class,
            'display_name': CLASS_DISPLAY_NAMES.get(predicted_class, predicted_class),
            'confidence': round(confidence, 4),
            'top_predictions': top_predictions,
            'all_probabilities': all_probabilities,
            'is_above_threshold': confidence >= threshold,
            'inference_time_ms': round(inference_time_ms, 2),
        })

        logger.info(
            f'Inference complete: {predicted_class} ({confidence:.2%}) in {inference_time_ms:.1f}ms'
        )

    except Exception as e:
        result['error'] = f'Inference error: {str(e)}'
        logger.error(result['error'])

    return result


def draw_bounding_boxes(image_path: str, boxes: list, output_path: str):
    """
    Draw bounding boxes on an image and save.
    boxes: list of {x1, y1, x2, y2, label, confidence}
    """
    try:
        import cv2
        img = cv2.imread(str(image_path))
        if img is None:
            return False

        for box in boxes:
            x1, y1, x2, y2 = int(box['x1']), int(box['y1']), int(box['x2']), int(box['y2'])
            label = box.get('label', '')
            conf = box.get('confidence', 0.0)

            # Draw rectangle
            cv2.rectangle(img, (x1, y1), (x2, y2), (37, 99, 235), 2)

            # Draw label background
            label_text = f'{label}: {conf:.1%}'
            (w, h), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(img, (x1, y1 - h - 10), (x1 + w, y1), (37, 99, 235), -1)
            cv2.putText(img, label_text, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imwrite(str(output_path), img)
        return True

    except Exception as e:
        logger.error(f'Bounding box drawing failed: {e}')
        return False


def get_active_model_path():
    """Get the path of the currently active/trained model.
    
    Checks for both Keras (.keras) and scikit-learn (.pkl) models.
    Returns the first available model file path.
    """
    model_dir = settings.AI_MODEL_DIR
    # Check for sklearn model first (works without TensorFlow)
    for filename in ['issuesnap_sklearn.pkl']:
        path = model_dir / filename
        if path.exists():
            return str(path)
    # Then check for Keras models
    for filename in ['issuesnap_efficientnet.keras', 'issuesnap_mobilenet.keras', 'issuesnap_cnn.keras']:
        path = model_dir / filename
        if path.exists():
            return str(path)
    return None
