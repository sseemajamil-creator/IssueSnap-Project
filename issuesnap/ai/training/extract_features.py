"""
IssueSnap Image Feature Extraction
Extracts real computer-vision features from images for scikit-learn classification.

Features extracted:
  - RGB color histograms (per channel, 32 bins each)
  - HSV color histograms (per channel, 32 bins each)  
  - HOG (Histogram of Oriented Gradients) descriptors
  - Edge density (Canny edge count)
  - LBP (Local Binary Pattern) texture histogram
  - Image statistics (mean, std per channel)

These are genuine, measurable image features — not random values.
"""
import numpy as np
from PIL import Image

# Category configuration
CATEGORIES = [
    'pothole',
    'garbage',
    'water_leakage',
    'broken_streetlight',
    'other',
]

CLASS_DISPLAY_NAMES = {
    'pothole': 'Road Pothole',
    'garbage': 'Garbage Overflow',
    'water_leakage': 'Water Leakage',
    'broken_streetlight': 'Broken Streetlight',
    'other': 'Other Civic Issue',
}

IMG_SIZE = (128, 128)  # Processing size for feature extraction


def extract_features(image_path: str) -> np.ndarray:
    """
    Extract a feature vector from an image file.
    Returns a 1D numpy array of ~1000 features.
    Returns None if the image cannot be loaded.
    """
    try:
        img = Image.open(image_path).convert('RGB')
    except Exception:
        return None

    img = img.resize(IMG_SIZE, Image.LANTCHOS if hasattr(Image, 'LANTCHOS') else Image.LANCZOS)
    arr = np.array(img, dtype=np.float32)

    features = []

    # ── 1. RGB color histograms (3 channels × 32 bins = 96 features) ──
    for ch in range(3):
        hist, _ = np.histogram(arr[:, :, ch], bins=32, range=(0, 256), density=True)
        features.extend(hist.tolist())

    # ── 2. HSV color histograms (3 channels × 32 bins = 96 features) ──
    import cv2
    hsv = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2HSV)
    for ch in range(3):
        hist, _ = np.histogram(hsv[:, :, ch], bins=32, range=(0, 256), density=True)
        features.extend(hist.tolist())

    # ── 3. HOG features (~324 features) ──
    try:
        from skimage.feature import hog as skhog
        hog_features = skhog(
            cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2GRAY),
            orientations=9,
            pixels_per_cell=(16, 16),
            cells_per_block=(2, 2),
            feature_vector=True,
        )
        features.extend(hog_features.tolist())
    except ImportError:
        # Fallback: use cv2.HOGDescriptor
        gray = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2GRAY)
        win_size = (128, 128)
        block_size = (16, 16)
        block_stride = (8, 8)
        cell_size = (8, 8)
        nbins = 9
        hog = cv2.HOGDescriptor(win_size, block_size, block_stride, cell_size, nbins)
        hog_features = hog.compute(gray).flatten()
        # Truncate or pad to consistent size
        max_hog = 324
        if len(hog_features) > max_hog:
            hog_features = hog_features[:max_hog]
        else:
            hog_features = np.pad(hog_features, (0, max_hog - len(hog_features)))
        features.extend(hog_features.tolist())

    # ── 4. Edge density ──
    edges = cv2.Canny(arr.astype(np.uint8), 50, 150)
    edge_density = float(np.sum(edges > 0)) / (edges.shape[0] * edges.shape[1])
    features.append(edge_density)

    # ── 5. Image statistics (6 features) ──
    for ch in range(3):
        features.append(float(np.mean(arr[:, :, ch])))
        features.append(float(np.std(arr[:, :, ch])))

    # ── 6. LBP texture histogram (26 features) ──
    gray = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    lbp = _local_binary_pattern(gray, P=8, R=1.0)
    lbp_hist, _ = np.histogram(lbp, bins=26, range=(0, 26), density=True)
    features.extend(lbp_hist.tolist())

    return np.array(features, dtype=np.float32)


def _local_binary_pattern(image, P=8, R=1.0):
    """Compute Local Binary Pattern texture descriptor."""
    try:
        from skimage.feature import local_binary_pattern
        return local_binary_pattern(image, P, R, method='uniform')
    except ImportError:
        # Simple LBP implementation
        h, w = image.shape
        lbp = np.zeros((h - 2, w - 2), dtype=np.float32)
        for i in range(1, h - 1):
            for j in range(1, w - 1):
                center = image[i, j]
                code = 0
                code |= (image[i - 1, j - 1] >= center) << 7
                code |= (image[i - 1, j] >= center) << 6
                code |= (image[i - 1, j + 1] >= center) << 5
                code |= (image[i, j + 1] >= center) << 4
                code |= (image[i + 1, j + 1] >= center) << 3
                code |= (image[i + 1, j] >= center) << 2
                code |= (image[i + 1, j - 1] >= center) << 1
                code |= (image[i, j - 1] >= center) << 0
                lbp[i - 1, j - 1] = code
        return lbp


def extract_features_batch(image_paths):
    """Extract features from a list of image paths. Returns (features_array, valid_indices)."""
    features_list = []
    valid_indices = []
    for idx, path in enumerate(image_paths):
        feat = extract_features(path)
        if feat is not None:
            features_list.append(feat)
            valid_indices.append(idx)
    if not features_list:
        return np.array([]), []
    return np.vstack(features_list), valid_indices
