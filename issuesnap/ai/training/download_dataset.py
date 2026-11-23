"""
IssueSnap Dataset Downloader
Downloads real sample images for each civic issue category from Wikimedia Commons
(free, Creative Commons licensed, no API key required).

Usage:
    python issuesnap/ai/training/download_dataset.py

Images are saved to:
    issuesnap/ai/datasets/raw/<category>/image_001.jpg
    issuesnap/ai/datasets/raw/<category>/image_002.jpg
    ...

Categories:
    pothole, garbage, water_leakage, broken_streetlight, other
"""
import os
import sys
import urllib.request
import urllib.parse
import json
import time
from pathlib import Path

DATASET_DIR = Path(__file__).parent.parent / 'datasets' / 'raw'

# Search terms for Wikimedia Commons API
SEARCH_TERMS = {
    'pothole': ['pothole road damage', 'road pothole', 'pothole street'],
    'garbage': ['garbage waste', 'trash pile street', 'litter rubbish'],
    'water_leakage': ['water leak pipe burst', 'water leakage road', 'flooded street'],
    'broken_streetlight': ['broken street lamp', 'street light damage', 'streetlight pole broken'],
    'other': ['damaged infrastructure', 'cracked wall', 'public property damage'],
}

IMAGES_PER_CATEGORY = 8


def search_wikimedia_commons(query, limit=10):
    """Search Wikimedia Commons for images matching the query."""
    base_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        'action': 'query',
        'format': 'json',
        'list': 'search',
        'srsearch': query,
        'srnamespace': '6',  # File namespace
        'srlimit': str(limit),
    }
    url = base_url + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'IssueSnap/1.0 (educational project)'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        results = []
        for item in data.get('query', {}).get('search', []):
            title = item.get('title', '')
            if title.startswith('File:'):
                results.append(title)
        return results
    except Exception as e:
        print(f'  Search failed for "{query}": {e}')
        return []


def get_image_url(file_title):
    """Get the direct download URL for a Wikimedia Commons file."""
    base_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        'action': 'query',
        'format': 'json',
        'titles': file_title,
        'prop': 'imageinfo',
        'iiprop': 'url|mime|size',
        'iiurlwidth': '300',
    }
    url = base_url + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'IssueSnap/1.0 (educational project)'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        pages = data.get('query', {}).get('pages', {})
        for page in pages.values():
            info = page.get('imageinfo', [{}])[0]
            mime = info.get('mime', '')
            if mime in ('image/jpeg', 'image/png'):
                return info.get('thumburl') or info.get('url')
    except Exception:
        pass
    return None


def download_image(url, save_path):
    """Download an image from URL and save to file."""
    req = urllib.request.Request(url, headers={'User-Agent': 'IssueSnap/1.0 (educational project)'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            if len(data) < 1000:  # Skip tiny/corrupt files
                return False
            with open(save_path, 'wb') as f:
                f.write(data)
            return True
    except Exception:
        return False


def main():
    print("=" * 60)
    print("IssueSnap Dataset Downloader")
    print("Source: Wikimedia Commons (CC licensed, free)")
    print("=" * 60)

    total_downloaded = 0

    for category, queries in SEARCH_TERMS.items():
        cat_dir = DATASET_DIR / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        existing = len(list(cat_dir.glob('*.jpg')))
        if existing >= IMAGES_PER_CATEGORY:
            print(f"[{category}] Already has {existing} images — skipping")
            total_downloaded += existing
            continue

        print(f"\n[{category}] Searching Wikimedia Commons...")
        downloaded = existing
        img_idx = existing + 1

        for query in queries:
            if downloaded >= IMAGES_PER_CATEGORY:
                break
            print(f"  Searching: '{query}'")
            files = search_wikimedia_commons(query, limit=10)
            time.sleep(1)  # Be polite to the API

            for file_title in files:
                if downloaded >= IMAGES_PER_CATEGORY:
                    break
                img_url = get_image_url(file_title)
                if not img_url:
                    continue
                save_path = cat_dir / f'image_{img_idx:03d}.jpg'
                if download_image(img_url, save_path):
                    print(f"    Downloaded: {save_path.name}")
                    downloaded += 1
                    img_idx += 1
                    time.sleep(0.5)
                else:
                    print(f"    Failed: {file_title}")

        total_downloaded += downloaded
        print(f"  [{category}] Total: {downloaded} images")

    print("\n" + "=" * 60)
    print(f"Dataset download complete. Total images: {total_downloaded}")
    print(f"Location: {DATASET_DIR}")

    # Summary
    for cat in SEARCH_TERMS:
        cat_dir = DATASET_DIR / cat
        count = len(list(cat_dir.glob('*.jpg'))) if cat_dir.exists() else 0
        status = "OK" if count >= 3 else "NEEDS MORE IMAGES"
        print(f"  {cat:<25} {count} images  [{status}]")

    return total_downloaded


if __name__ == '__main__':
    main()
