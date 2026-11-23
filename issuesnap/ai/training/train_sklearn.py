"""
IssueSnap Model Training — scikit-learn Edition
=================================================
Trains a Random Forest image classifier on real computer-vision features
extracted from civic issue images. No TensorFlow/Keras required.

Features used:
  - RGB + HSV color histograms
  - HOG (Histogram of Oriented Gradients)  
  - Edge density (Canny)
  - LBP texture histograms
  - Image statistics (mean, std per channel)

Usage:
    python issuesnap/ai/training/train_sklearn.py

Prerequisites:
    - Run download_dataset.py first to get training images
    - Or manually place images in issuesnap/ai/datasets/raw/<category>/

Output:
    Model saved to: issuesnap/ai/models/issuesnap_sklearn.pkl
    Evaluation saved to: issuesnap/ai/evaluation/results/eval_sklearn.json
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)
import joblib

from issuesnap.ai.training.extract_features import (
    extract_features, CATEGORIES, CLASS_DISPLAY_NAMES
)

DATASET_DIR = Path(__file__).parent.parent / 'datasets' / 'raw'
MODEL_DIR = Path(__file__).parent.parent / 'models'
RESULTS_DIR = Path(__file__).parent.parent / 'evaluation' / 'results'


def load_dataset():
    """Load all images from the dataset directory and extract features."""
    X = []
    y = []
    category_counts = {}

    for cat_idx, category in enumerate(CATEGORIES):
        cat_dir = DATASET_DIR / category
        if not cat_dir.exists():
            print(f"  [SKIP] No directory for: {category}")
            category_counts[category] = 0
            continue

        image_files = sorted(
            list(cat_dir.glob('*.jpg')) + list(cat_dir.glob('*.jpeg')) +
            list(cat_dir.glob('*.png')) + list(cat_dir.glob('*.webp'))
        )

        count = 0
        for img_path in image_files:
            features = extract_features(str(img_path))
            if features is not None:
                X.append(features)
                y.append(cat_idx)
                count += 1

        category_counts[category] = count
        print(f"  {category:<25} {count} images loaded")

    return np.array(X), np.array(y), category_counts


def train():
    print("=" * 60)
    print("IssueSnap Model Training (scikit-learn)")
    print("=" * 60)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Load dataset ──────────────────────────────────────────
    print("\n[1/5] Loading dataset and extracting features...")
    X, y, cat_counts = load_dataset()

    total_images = len(X)
    if total_images < 5:
        print(f"\n[ERROR] Only {total_images} images found. Need at least 5.")
        print(f"Run: python issuesnap/ai/training/download_dataset.py")
        print(f"Or manually place images in: {DATASET_DIR}/<category>/")
        return False

    print(f"\n  Total images: {total_images}")
    print(f"  Feature vector size: {X.shape[1]}")

    # Check for categories with 0 images
    empty_cats = [c for c, n in cat_counts.items() if n == 0]
    if empty_cats:
        print(f"\n  [WARNING] No images for: {', '.join(empty_cats)}")
        print(f"  These categories will not be classifiable.")

    # Filter to only categories that have images
    valid_indices = [i for i, label in enumerate(y) if cat_counts[CATEGORIES[label]] > 0]
    X = X[valid_indices]
    y = y[valid_indices]

    # ── 2. Split into train/test ────────────────────────────────
    print("\n[2/5] Splitting dataset...")
    if total_images >= 10:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
        )
    else:
        # Too few for a split — use all for training, test on same
        X_train, X_test = X, X
        y_train, y_test = y, y

    print(f"  Train: {len(X_train)} samples")
    print(f"  Test:  {len(X_test)} samples")

    # ── 3. Train classifier ─────────────────────────────────────
    print("\n[3/5] Training Random Forest classifier...")
    t_start = time.time()

    classifier = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        min_samples_split=2,
        min_samples_leaf=1,
        random_state=42,
        class_weight='balanced',
    )
    classifier.fit(X_train, y_train)

    train_time = time.time() - t_start
    print(f"  Training time: {train_time:.1f}s")

    # ── 4. Evaluate ─────────────────────────────────────────────
    print("\n[4/5] Evaluating model...")
    y_pred = classifier.predict(X_test)
    y_pred_proba = classifier.predict_proba(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
    f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    # Per-class report
    valid_cats = [c for c in CATEGORIES if cat_counts.get(c, 0) > 0]
    report = classification_report(
        y_test, y_pred,
        target_names=[CLASS_DISPLAY_NAMES.get(c, c) for c in valid_cats],
        output_dict=True, zero_division=0
    )

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred).tolist()

    # Inference time
    t_inf_start = time.time()
    for i in range(min(10, len(X_test))):
        classifier.predict(X_test[i:i+1])
    avg_inference_ms = ((time.time() - t_inf_start) / max(len(X_test), 1)) * 1000

    print(f"\n  Accuracy:   {accuracy*100:.1f}%")
    print(f"  Precision:  {precision*100:.1f}%")
    print(f"  Recall:     {recall*100:.1f}%")
    print(f"  F1-Score:   {f1*100:.1f}%")
    print(f"  Inference:  {avg_inference_ms:.1f}ms per image")
    print(f"\n  Confusion Matrix:")
    print(f"  {cm}")

    # ── 5. Save model ────────────────────────────────────────────
    print("\n[5/5] Saving model...")
    model_path = MODEL_DIR / 'issuesnap_sklearn.pkl'

    model_package = {
        'classifier': classifier,
        'categories': CATEGORIES,
        'class_display_names': CLASS_DISPLAY_NAMES,
        'feature_count': X.shape[1],
        'training_info': {
            'total_images': total_images,
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'category_counts': cat_counts,
            'training_time_seconds': round(train_time, 2),
            'trained_at': datetime.now().isoformat(),
            'model_type': 'RandomForest',
            'n_estimators': 100,
            'feature_extraction': 'RGB_HSV_histograms + HOG + LBP + edge_density + stats',
        },
        'metrics': {
            'accuracy': round(accuracy, 4),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1_score': round(f1, 4),
            'avg_inference_ms': round(avg_inference_ms, 2),
            'confusion_matrix': cm,
            'per_class': {
                cat: {
                    'precision': round(report.get(cat, {}).get('precision', 0), 4),
                    'recall': round(report.get(cat, {}).get('recall', 0), 4),
                    'f1': round(report.get(cat, {}).get('f1-score', 0), 4),
                    'support': int(report.get(cat, {}).get('support', 0)),
                }
                for cat in valid_cats
            }
        }
    }

    joblib.dump(model_package, model_path)
    print(f"  Model saved to: {model_path}")

    # Save evaluation results
    eval_path = RESULTS_DIR / 'eval_sklearn.json'
    with open(eval_path, 'w') as f:
        json.dump(model_package['metrics'], f, indent=2)
    print(f"  Evaluation saved to: {eval_path}")

    # ── Summary ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"  Model type:        Random Forest (scikit-learn)")
    print(f"  Training images:   {total_images}")
    print(f"  Feature vector:    {X.shape[1]} features")
    print(f"  Test accuracy:     {accuracy*100:.1f}%")
    print(f"  F1-Score:          {f1*100:.1f}%")
    print(f"  Inference time:    {avg_inference_ms:.1f}ms per image")
    print(f"  Model file:        {model_path}")

    print(f"\n  To register in Django admin:")
    print(f"  1. Go to /django-admin/ai_engine/modelversion/add/")
    print(f"  2. Set: model_type='mobilenetv2' (closest match)")
    print(f"  3. Set accuracy={accuracy*100:.1f}%, f1_score={f1*100:.1f}%")
    print(f"  4. Set is_trained=True, is_active=True")

    return True


if __name__ == '__main__':
    train()
