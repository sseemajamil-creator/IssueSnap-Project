"""
IssueSnap Dataset Preparation Script
=====================================
Prepares the civic issue dataset for training.

Supported source dataset structure:
  ai/datasets/raw/<category_name>/*.jpg

Output structure:
  ai/datasets/processed/train/<category>/*.jpg
  ai/datasets/processed/val/<category>/*.jpg
  ai/datasets/processed/test/<category>/*.jpg

Usage:
  python issuesnap/ai/training/prepare_dataset.py

Requirements:
  pip install scikit-learn pillow opencv-python numpy tqdm
"""

import os
import sys
import shutil
import random
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

SUPPORTED_CATEGORIES = [
    'pothole',
    'road_crack',
    'garbage',
    'water_leakage',
    'drainage_blockage',
    'broken_streetlight',
    'damaged_infrastructure',
]

RAW_DIR = Path(__file__).parent.parent / 'datasets' / 'raw'
PROCESSED_DIR = Path(__file__).parent.parent / 'datasets' / 'processed'

TRAIN_SPLIT = 0.70
VAL_SPLIT   = 0.15
TEST_SPLIT  = 0.15

VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}


def prepare_dataset():
    print("=" * 60)
    print("IssueSnap Dataset Preparation")
    print("=" * 60)

    if not RAW_DIR.exists():
        print(f"\n[ERROR] Raw dataset directory not found: {RAW_DIR}")
        print("\nExpected structure:")
        for cat in SUPPORTED_CATEGORIES:
            print(f"  ai/datasets/raw/{cat}/*.jpg")
        print("\nPlease download datasets from:")
        print("  - RDD2022 (road damage): https://github.com/sekilab/RoadDamageDetector")
        print("  - TACO (garbage): http://tacodataset.org/")
        print("  - Roboflow Pothole: https://universe.roboflow.com/")
        return False

    # Create split directories
    for split in ['train', 'val', 'test']:
        for cat in SUPPORTED_CATEGORIES:
            (PROCESSED_DIR / split / cat).mkdir(parents=True, exist_ok=True)

    total_stats = {}

    for cat in SUPPORTED_CATEGORIES:
        cat_dir = RAW_DIR / cat
        if not cat_dir.exists():
            print(f"\n[SKIP] Category directory not found: {cat_dir}")
            continue

        # Gather valid images
        images = [
            f for f in cat_dir.iterdir()
            if f.suffix.lower() in VALID_EXTENSIONS
        ]

        if len(images) == 0:
            print(f"\n[SKIP] No images in {cat_dir}")
            continue

        # Shuffle for random split (fixed seed for reproducibility)
        random.seed(42)
        random.shuffle(images)

        n = len(images)
        n_train = int(n * TRAIN_SPLIT)
        n_val   = int(n * VAL_SPLIT)
        # Remaining go to test to avoid rounding loss
        n_test  = n - n_train - n_val

        splits = {
            'train': images[:n_train],
            'val':   images[n_train:n_train + n_val],
            'test':  images[n_train + n_val:],
        }

        for split, files in splits.items():
            for src in files:
                dst = PROCESSED_DIR / split / cat / src.name
                shutil.copy2(src, dst)

        total_stats[cat] = {'train': n_train, 'val': n_val, 'test': n_test, 'total': n}
        print(f"[OK] {cat}: {n} images → train:{n_train} val:{n_val} test:{n_test}")

    print("\n" + "=" * 60)
    print("Dataset Preparation Summary")
    print("=" * 60)
    for cat, s in total_stats.items():
        print(f"  {cat:<30} total:{s['total']:<6} train:{s['train']:<6} val:{s['val']:<6} test:{s['test']}")

    total_imgs = sum(s['total'] for s in total_stats.values())
    print(f"\n  Total images: {total_imgs}")
    print(f"  Output: {PROCESSED_DIR}")
    print("\nDataset ready. Run train_model.py to start training.")
    return True


if __name__ == '__main__':
    prepare_dataset()
