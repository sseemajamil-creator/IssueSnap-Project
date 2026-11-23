"""Register the trained sklearn model in Django's ModelVersion table."""
import os, sys, json
os.chdir(r"c:\Users\seemajamil\OneDrive\Desktop\issuesnap")
sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "issuesnap.config.settings")
import django; django.setup()

import joblib
from pathlib import Path
from issuesnap.apps.ai_engine.models import ModelVersion

MODEL_PATH = Path("issuesnap/ai/models/issuesnap_sklearn.pkl")
EVAL_PATH = Path("issuesnap/ai/evaluation/results/eval_sklearn.json")

# Load model package for metadata
pkg = joblib.load(MODEL_PATH)
metrics = pkg.get('metrics', {})
info = pkg.get('training_info', {})

# Load eval JSON if available
eval_data = {}
if EVAL_PATH.exists():
    with open(EVAL_PATH) as f:
        eval_data = json.load(f)

# Deactivate any existing active models
ModelVersion.objects.filter(is_active=True).update(is_active=False)

# Create or update the model version record
mv, created = ModelVersion.objects.update_or_create(
    name='IssueSnap Image Classifier',
    version='1.0',
    defaults={
        'model_type': 'random_forest',
        'description': 'Random Forest classifier (scikit-learn) on computer-vision features (color histograms, HOG, LBP, edge density). Trained on real Wikimedia Commons images.',
        'model_file': 'issuesnap_sklearn.pkl',
        'input_size': 128,
        'num_classes': len(pkg.get('categories', [])),
        'class_names': pkg.get('categories', []),
        'is_active': True,
        'is_trained': True,
        'accuracy': metrics.get('accuracy', 0.375),
        'precision': metrics.get('precision', 0.458),
        'recall': metrics.get('recall', 0.375),
        'f1_score': metrics.get('f1_score', 0.392),
        'inference_time_ms': metrics.get('avg_inference_ms', 6.8),
        'training_dataset': 'Wikimedia Commons (CC licensed)',
        'training_samples': info.get('train_samples', 24),
        'validation_samples': 0,
        'test_samples': info.get('test_samples', 8),
        'epochs_trained': 100,  # n_estimators for RF
    }
)

print(f"ModelVersion {'created' if created else 'updated'}: {mv}")
print(f"  Active: {mv.is_active}")
print(f"  Trained: {mv.is_trained}")
print(f"  Accuracy: {mv.accuracy*100:.1f}%")
print(f"  F1: {mv.f1_score*100:.1f}%")
print(f"  Classes: {mv.class_names}")
print(f"  Model file: {mv.model_file}")
