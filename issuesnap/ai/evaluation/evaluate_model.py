"""
IssueSnap Model Evaluation Script
====================================
Evaluates a trained model on the test set and prints:
  - Accuracy, Precision, Recall, F1-Score
  - Per-class metrics
  - Confusion matrix
  - Average inference time

Usage:
  python issuesnap/ai/evaluation/evaluate_model.py --model mobilenetv2

Output is saved to ai/evaluation/results/ and can be registered in Django admin.
"""

import os
import sys
import json
import time
import argparse
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

DATASET_DIR = Path(__file__).parent.parent / 'datasets' / 'processed'
MODEL_DIR   = Path(__file__).parent.parent / 'models'
RESULTS_DIR = Path(__file__).parent / 'results'

IMG_SIZE = 224
CATEGORIES = [
    'pothole', 'road_crack', 'garbage',
    'water_leakage', 'drainage_blockage',
    'broken_streetlight', 'damaged_infrastructure',
]


def evaluate(args):
    import tensorflow as tf
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        confusion_matrix, classification_report
    )

    model_path = MODEL_DIR / f'issuesnap_{args.model}.keras'
    if not model_path.exists():
        print(f"[ERROR] Model not found at {model_path}")
        print("Train the model first with train_model.py")
        return

    test_dir = DATASET_DIR / 'test'
    if not test_dir.exists():
        print(f"[ERROR] Test dataset not found at {test_dir}")
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Loading model: {model_path}")
    model = tf.keras.models.load_model(str(model_path))

    # Load test data
    from tensorflow.keras.preprocessing.image import ImageDataGenerator
    test_datagen = ImageDataGenerator(rescale=1.0/255)
    test_gen = test_datagen.flow_from_directory(
        test_dir,
        target_size=(IMG_SIZE, IMG_SIZE),
        batch_size=1,
        class_mode='categorical',
        shuffle=False,
    )

    if test_gen.samples == 0:
        print("[ERROR] No test images found.")
        return

    print(f"[INFO] Evaluating on {test_gen.samples} test images...")

    y_true = []
    y_pred = []
    inference_times = []

    for i in range(test_gen.samples):
        img_batch, label_batch = next(test_gen)
        t0 = time.time()
        pred = model.predict(img_batch, verbose=0)
        t1 = time.time()
        inference_times.append((t1 - t0) * 1000)

        y_true.append(np.argmax(label_batch[0]))
        y_pred.append(np.argmax(pred[0]))

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    # Metrics
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, average='weighted', zero_division=0)
    rec = recall_score(y_true, y_pred, average='weighted', zero_division=0)
    f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0)
    cm = confusion_matrix(y_true, y_pred).tolist()
    avg_inference = np.mean(inference_times)

    # Per-class
    report = classification_report(y_true, y_pred, target_names=CATEGORIES, output_dict=True, zero_division=0)

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"  Accuracy:   {acc:.4f}  ({acc*100:.1f}%)")
    print(f"  Precision:  {prec:.4f} ({prec*100:.1f}%)")
    print(f"  Recall:     {rec:.4f}  ({rec*100:.1f}%)")
    print(f"  F1-Score:   {f1:.4f}  ({f1*100:.1f}%)")
    print(f"  Avg Inference: {avg_inference:.1f}ms")
    print("\nPer-class metrics:")
    for cat in CATEGORIES:
        m = report.get(cat, {})
        print(f"  {cat:<30} P:{m.get('precision',0)*100:.1f}% R:{m.get('recall',0)*100:.1f}% F1:{m.get('f1-score',0)*100:.1f}%")

    # Save results
    results = {
        'model': args.model,
        'test_samples': test_gen.samples,
        'accuracy': round(acc, 4),
        'precision': round(prec, 4),
        'recall': round(rec, 4),
        'f1_score': round(f1, 4),
        'avg_inference_ms': round(avg_inference, 2),
        'confusion_matrix': cm,
        'per_class_metrics': {
            cat: {
                'precision': round(report[cat].get('precision', 0), 4),
                'recall': round(report[cat].get('recall', 0), 4),
                'f1': round(report[cat].get('f1-score', 0), 4),
                'support': int(report[cat].get('support', 0)),
            }
            for cat in CATEGORIES if cat in report
        },
        'categories': CATEGORIES,
    }

    result_path = RESULTS_DIR / f'eval_{args.model}.json'
    with open(result_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n[INFO] Results saved to {result_path}")
    print(f"\nTo register in Django:")
    print(f"  1. Open Django admin: /django-admin/ai_engine/modelversion/")
    print(f"  2. Update accuracy: {acc*100:.1f}%, precision: {prec*100:.1f}%, recall: {rec*100:.1f}%, f1: {f1*100:.1f}%")
    print(f"  3. Set is_trained=True, is_active=True")
    print(f"  4. Register as ResearchExperiment in /django-admin/research/researchexperiment/")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['mobilenetv2', 'efficientnet'], default='mobilenetv2')
    args = parser.parse_args()
    evaluate(args)
