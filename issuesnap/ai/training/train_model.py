"""
IssueSnap Model Training Script
=================================
Trains a MobileNetV2 or EfficientNetB0 model on the civic issue dataset
using transfer learning with TensorFlow/Keras.

Prerequisites:
  - Run prepare_dataset.py first
  - Install: pip install tensorflow opencv-python-headless numpy matplotlib

Usage:
  python issuesnap/ai/training/train_model.py --model mobilenetv2 --epochs 30
  python issuesnap/ai/training/train_model.py --model efficientnet --epochs 50

The trained model is saved to:
  issuesnap/ai/models/issuesnap_<model_type>.keras
"""

import os
import sys
import argparse
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

DATASET_DIR = Path(__file__).parent.parent / 'datasets' / 'processed'
MODEL_DIR   = Path(__file__).parent.parent / 'models'
LOG_DIR     = Path(__file__).parent.parent / 'training' / 'logs'

CATEGORIES = [
    'pothole', 'road_crack', 'garbage',
    'water_leakage', 'drainage_blockage',
    'broken_streetlight', 'damaged_infrastructure',
]

IMG_SIZE = 224
BATCH_SIZE = 32
INITIAL_EPOCHS = 10  # Phase 1: train top layers only
FINE_TUNE_EPOCHS = 20  # Phase 2: fine-tune last layers


def build_model(model_type: str, num_classes: int):
    import tensorflow as tf
    from tensorflow.keras import layers, Model
    from tensorflow.keras.applications import MobileNetV2, EfficientNetB0

    if model_type == 'mobilenetv2':
        base = MobileNetV2(
            input_shape=(IMG_SIZE, IMG_SIZE, 3),
            include_top=False,
            weights='imagenet'
        )
        base.trainable = False
        print(f"[INFO] MobileNetV2 base loaded: {len(base.layers)} layers (frozen)")
    elif model_type == 'efficientnet':
        base = EfficientNetB0(
            input_shape=(IMG_SIZE, IMG_SIZE, 3),
            include_top=False,
            weights='imagenet'
        )
        base.trainable = False
        print(f"[INFO] EfficientNetB0 base loaded: {len(base.layers)} layers (frozen)")
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Classification head
    x = base.output
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dense(256, activation='relu')(x)
    x = layers.Dropout(0.4)(x)
    outputs = layers.Dense(num_classes, activation='softmax')(x)

    model = Model(inputs=base.input, outputs=outputs)
    return model, base


def get_data_generators():
    from tensorflow.keras.preprocessing.image import ImageDataGenerator

    train_datagen = ImageDataGenerator(
        rescale=1.0/255,
        rotation_range=20,
        width_shift_range=0.15,
        height_shift_range=0.15,
        horizontal_flip=True,
        vertical_flip=False,
        zoom_range=0.15,
        brightness_range=[0.8, 1.2],
        fill_mode='nearest',
    )

    val_datagen = ImageDataGenerator(rescale=1.0/255)

    train_gen = train_datagen.flow_from_directory(
        DATASET_DIR / 'train',
        target_size=(IMG_SIZE, IMG_SIZE),
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        shuffle=True,
        seed=42,
    )

    val_gen = val_datagen.flow_from_directory(
        DATASET_DIR / 'val',
        target_size=(IMG_SIZE, IMG_SIZE),
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        shuffle=False,
    )

    return train_gen, val_gen


def train(args):
    import tensorflow as tf
    print(f"\nTensorFlow version: {tf.__version__}")
    print(f"GPUs: {tf.config.list_physical_devices('GPU')}")

    if not (DATASET_DIR / 'train').exists():
        print(f"[ERROR] Training dataset not found at {DATASET_DIR}/train")
        print("Run prepare_dataset.py first.")
        return

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    num_classes = len(CATEGORIES)
    print(f"\n[INFO] Classes: {CATEGORIES}")
    print(f"[INFO] Num classes: {num_classes}")

    # Data generators
    train_gen, val_gen = get_data_generators()
    print(f"[INFO] Train samples: {train_gen.samples}")
    print(f"[INFO] Val samples: {val_gen.samples}")
    print(f"[INFO] Class indices: {train_gen.class_indices}")

    # Build model
    model, base = build_model(args.model, num_classes)
    model.summary()

    # Phase 1: Train head only
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )

    callbacks_phase1 = [
        tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=3, verbose=1),
    ]

    print(f"\n[PHASE 1] Training top layers ({INITIAL_EPOCHS} epochs)...")
    t_start = time.time()
    history1 = model.fit(
        train_gen,
        epochs=INITIAL_EPOCHS,
        validation_data=val_gen,
        callbacks=callbacks_phase1,
        verbose=1,
    )

    # Phase 2: Fine-tune last N layers of base
    print(f"\n[PHASE 2] Fine-tuning last 20 layers ({args.epochs} more epochs)...")
    base.trainable = True
    # Freeze all but last 20 layers
    for layer in base.layers[:-20]:
        layer.trainable = False

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )

    model_save_path = MODEL_DIR / f'issuesnap_{args.model}.keras'
    callbacks_phase2 = [
        tf.keras.callbacks.EarlyStopping(patience=8, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=4, verbose=1),
        tf.keras.callbacks.ModelCheckpoint(
            str(model_save_path),
            save_best_only=True,
            monitor='val_accuracy',
            verbose=1
        ),
    ]

    history2 = model.fit(
        train_gen,
        epochs=args.epochs,
        validation_data=val_gen,
        callbacks=callbacks_phase2,
        verbose=1,
    )

    training_time = (time.time() - t_start) / 60.0

    # Save training history
    combined_history = {}
    for key in history1.history:
        combined_history[key] = history1.history[key] + history2.history.get(key, [])

    history_path = LOG_DIR / f'training_history_{args.model}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(history_path, 'w') as f:
        json.dump(combined_history, f, indent=2)

    best_val_acc = max(combined_history.get('val_accuracy', [0]))
    print(f"\n{'='*60}")
    print(f"TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"Model saved to: {model_save_path}")
    print(f"Best val accuracy: {best_val_acc:.4f} ({best_val_acc*100:.1f}%)")
    print(f"Total training time: {training_time:.1f} minutes")
    print(f"\nNext step: Run evaluate_model.py to get full test metrics.")
    print(f"Then register in Django admin: AI Engine → Model Versions")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train IssueSnap AI model')
    parser.add_argument('--model', choices=['mobilenetv2', 'efficientnet'], default='mobilenetv2')
    parser.add_argument('--epochs', type=int, default=20, help='Fine-tune epochs')
    args = parser.parse_args()
    train(args)
