"""
IssueSnap NLP Analysis
Text analysis using TF-IDF, keyword extraction, and cosine similarity
"""
import re
import logging
import pickle
import numpy as np
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Urgency keywords
URGENCY_KEYWORDS = [
    'dangerous', 'urgent', 'emergency', 'severe', 'critical', 'immediate',
    'accident', 'injury', 'flood', 'collapse', 'broken', 'hazard', 'fatal',
    'unsafe', 'risk', 'blocked', 'overflow', 'leaking', 'burst', 'exposed',
]

# Category-related keyword mappings
CATEGORY_KEYWORDS = {
    'pothole': ['pothole', 'hole', 'pit', 'crater', 'depression', 'ditch', 'bump'],
    'road_crack': ['crack', 'cracks', 'cracked', 'fracture', 'split', 'break', 'pavement'],
    'garbage': ['garbage', 'waste', 'trash', 'litter', 'rubbish', 'dump', 'overflow', 'smell', 'bins'],
    'water_leakage': ['water', 'leak', 'leaking', 'pipe', 'burst', 'flood', 'wet', 'puddle', 'flowing'],
    'drainage_blockage': ['drain', 'drainage', 'blocked', 'clog', 'sewer', 'manhole', 'stagnant'],
    'broken_streetlight': ['light', 'streetlight', 'lamp', 'dark', 'night', 'pole', 'electric', 'bulb'],
    'damaged_infrastructure': ['wall', 'bridge', 'structure', 'damage', 'collapsed', 'foundation', 'building'],
}


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ''
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text: str) -> List[str]:
    """Simple word tokenizer."""
    return text.split()


def remove_stopwords(tokens: List[str]) -> List[str]:
    """Remove common English stopwords."""
    stopwords = {
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
        'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'this', 'that',
        'these', 'those', 'i', 'my', 'we', 'our', 'you', 'your', 'it',
        'its', 'very', 'also', 'just', 'not', 'no', 'so', 'up', 'out',
        'as', 'if', 'than', 'then', 'too', 'more', 'most', 'such',
    }
    return [t for t in tokens if t not in stopwords and len(t) > 2]


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """Extract keywords using frequency and relevance scoring."""
    cleaned = clean_text(text)
    tokens = tokenize(cleaned)
    tokens = remove_stopwords(tokens)

    if not tokens:
        return []

    freq = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1

    sorted_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in sorted_keywords[:top_n]]


def detect_urgency(text: str) -> Tuple[bool, List[str]]:
    """Detect urgency keywords in text."""
    cleaned = clean_text(text)
    found = [kw for kw in URGENCY_KEYWORDS if kw in cleaned]
    is_urgent = len(found) > 0
    return is_urgent, found


def suggest_category(title: str, description: str) -> Tuple[Optional[str], float]:
    """Suggest a complaint category based on text analysis."""
    combined = clean_text(f'{title} {description}')
    tokens = set(tokenize(combined))

    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        overlap = sum(1 for kw in keywords if kw in combined)
        if overlap > 0:
            scores[category] = overlap / len(keywords)

    if not scores:
        return None, 0.0

    best_category = max(scores, key=scores.get)
    confidence = min(scores[best_category], 1.0)

    return best_category, confidence


def compute_text_similarity(text1: str, text2: str) -> float:
    """
    Compute cosine similarity between two texts using TF-IDF.
    Returns float between 0.0 and 1.0.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        clean1 = clean_text(text1)
        clean2 = clean_text(text2)

        if not clean1 or not clean2:
            return 0.0

        vectorizer = TfidfVectorizer(min_df=1, stop_words='english')
        tfidf_matrix = vectorizer.fit_transform([clean1, clean2])
        sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return float(sim[0][0])

    except Exception as e:
        logger.error(f'Text similarity computation failed: {e}')
        return 0.0


def analyze_complaint_text(complaint) -> Dict:
    """
    Full NLP analysis of a complaint's text.
    Returns dict with all analysis results.
    """
    text = f'{complaint.title} {complaint.description}'
    cleaned = clean_text(text)

    keywords = extract_keywords(text, top_n=10)
    is_urgent, urgency_kws = detect_urgency(text)
    suggested_cat, cat_confidence = suggest_category(complaint.title, complaint.description)

    return {
        'cleaned_text': cleaned,
        'extracted_keywords': keywords,
        'urgency_keywords': urgency_kws,
        'is_urgent': is_urgent,
        'suggested_category': suggested_cat or '',
        'category_confidence': cat_confidence,
    }


def compute_geographic_distance(lat1, lon1, lat2, lon2) -> Optional[float]:
    """
    Compute geographic distance between two points using Haversine formula.
    Returns distance in kilometers.
    """
    if any(v is None for v in [lat1, lon1, lat2, lon2]):
        return None

    try:
        import math
        R = 6371  # Earth radius in km
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        dphi = math.radians(float(lat2) - float(lat1))
        dlambda = math.radians(float(lon2) - float(lon1))

        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 3)
    except Exception as e:
        logger.error(f'Distance computation failed: {e}')
        return None
