"""
IssueSnap AI Tasks
Called synchronously after complaint submission.
All failures are logged and do NOT crash the submission flow.
"""
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

DUPLICATE_THRESHOLD = 0.65
GEOGRAPHIC_THRESHOLD_KM = 2.0


def analyze_complaint_images(complaint_id: int):
    """
    Run AI image classification on all images of a complaint.
    Saves results to AIClassification model.
    """
    try:
        from issuesnap.apps.complaints.models import Complaint
        from issuesnap.apps.ai_engine.models import AIClassification, ModelVersion
        from issuesnap.apps.ai_engine.inference import run_inference, get_active_model_path
        from issuesnap.apps.notifications.models import Notification

        complaint = Complaint.objects.get(id=complaint_id)
        images = complaint.images.all()

        if not images.exists():
            logger.warning(f'No images for complaint {complaint.complaint_id}')
            return

        model_path = get_active_model_path()
        threshold = settings.AI_CONFIDENCE_THRESHOLD

        # No trained model available — mark as analyzed (attempted) and return.
        # run_inference must NOT be called with model_path=None.
        if model_path is None:
            logger.info(
                f'No trained model found for complaint {complaint.complaint_id}. '
                f'Skipping inference. Train a model and place it in AI_MODEL_DIR.'
            )
            complaint.ai_analyzed = True
            complaint.save(update_fields=['ai_analyzed'])
            _run_nlp_analysis(complaint)
            return

        # Get active model version record
        model_version = ModelVersion.objects.filter(is_active=True, is_trained=True).first()

        any_success = False
        for img in images:
            try:
                # Guard: ensure the image file has a usable path before inference.
                try:
                    img_path = img.image.path
                except (ValueError, AttributeError):
                    logger.error(
                        f'Image {img.id} for complaint {complaint.complaint_id} '
                        f'has no file path — skipping inference for this image.'
                    )
                    continue

                result = run_inference(img_path, model_path, threshold)

                AIClassification.objects.create(
                    complaint=complaint,
                    complaint_image=img,
                    model_version=model_version,
                    predicted_class=result.get('predicted_class', 'unknown'),
                    confidence_score=result.get('confidence', 0.0),
                    top_predictions=result.get('top_predictions', []),
                    all_class_probabilities=result.get('all_probabilities', {}),
                    is_above_threshold=result.get('is_above_threshold', False),
                    threshold_used=threshold,
                    inference_time_ms=result.get('inference_time_ms'),
                )
                if result.get('success'):
                    any_success = True
            except Exception as img_err:
                logger.error(f'AI inference failed for image {img.id}: {img_err}')

        complaint.ai_analyzed = True
        complaint.save(update_fields=['ai_analyzed'])

        if any_success:
            Notification.objects.create(
                user=complaint.citizen,
                title='AI Analysis Complete',
                message=f'AI analysis for complaint {complaint.complaint_id} is complete.',
                notification_type='ai_analyzed',
                complaint=complaint,
            )

        # Run NLP analysis
        _run_nlp_analysis(complaint)

    except Exception as e:
        logger.error(f'AI analysis task failed for complaint {complaint_id}: {e}')


def _run_nlp_analysis(complaint):
    """Run NLP analysis on complaint text."""
    try:
        from issuesnap.apps.ai_engine.models import NLPAnalysis
        from issuesnap.apps.ai_engine.nlp_analysis import analyze_complaint_text

        analysis_data = analyze_complaint_text(complaint)
        NLPAnalysis.objects.update_or_create(
            complaint=complaint,
            defaults=analysis_data,
        )
    except Exception as e:
        logger.error(f'NLP analysis failed for complaint {complaint.complaint_id}: {e}')


def detect_duplicates(complaint_id: int):
    """
    Detect potential duplicate complaints using TF-IDF cosine similarity,
    category matching, and geographic proximity.
    """
    try:
        from issuesnap.apps.complaints.models import Complaint, DuplicateComplaintMatch
        from issuesnap.apps.ai_engine.nlp_analysis import compute_text_similarity, compute_geographic_distance

        complaint = Complaint.objects.get(id=complaint_id)

        # Compare against recent complaints (last 90 days) in same/nearby category
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=90)

        candidates = Complaint.objects.filter(
            submitted_at__gte=cutoff,
        ).exclude(id=complaint_id).select_related('category')[:200]

        complaint_text = f'{complaint.title} {complaint.description}'

        for candidate in candidates:
            try:
                candidate_text = f'{candidate.title} {candidate.description}'

                # Text similarity
                text_sim = compute_text_similarity(complaint_text, candidate_text)

                # Category match
                cat_match = (complaint.category_id == candidate.category_id)

                # Geographic distance
                geo_dist = compute_geographic_distance(
                    complaint.latitude, complaint.longitude,
                    candidate.latitude, candidate.longitude
                )

                # Combined score
                score = text_sim * 0.6
                if cat_match:
                    score += 0.2
                if geo_dist is not None and geo_dist < GEOGRAPHIC_THRESHOLD_KM:
                    score += 0.2 * (1 - geo_dist / GEOGRAPHIC_THRESHOLD_KM)

                if score >= DUPLICATE_THRESHOLD:
                    DuplicateComplaintMatch.objects.get_or_create(
                        original_complaint=candidate,
                        duplicate_complaint=complaint,
                        defaults={
                            'similarity_score': round(score, 4),
                            'text_similarity': round(text_sim, 4),
                            'geographic_distance_km': geo_dist,
                            'category_match': cat_match,
                            'detection_method': 'tfidf_cosine_geo',
                        }
                    )
            except Exception as cand_err:
                logger.warning(f'Duplicate check failed for candidate {candidate.complaint_id}: {cand_err}')

    except Exception as e:
        logger.error(f'Duplicate detection failed for complaint {complaint_id}: {e}')


def predict_priority(complaint_id: int):
    """
    Predict complaint priority using a transparent rule-based system.
    Rules consider: category, urgency keywords, AI confidence, duplicate status.
    """
    try:
        from issuesnap.apps.complaints.models import Complaint, PriorityPrediction
        from issuesnap.apps.ai_engine.nlp_analysis import detect_urgency

        complaint = Complaint.objects.get(id=complaint_id)
        text = f'{complaint.title} {complaint.description}'
        is_urgent, urgency_kws = detect_urgency(text)

        # Rule-based scoring
        score = 0
        reasoning = {}

        # Category-based weight
        high_priority_categories = ['pothole', 'water_leakage', 'drainage_blockage']
        critical_categories = []

        if complaint.category:
            if complaint.category.slug in critical_categories:
                score += 40
                reasoning['category'] = 'Critical infrastructure category'
            elif complaint.category.slug in high_priority_categories:
                score += 30
                reasoning['category'] = 'High-priority infrastructure category'
            else:
                score += 15
                reasoning['category'] = 'Standard category'

        # Urgency keywords
        if is_urgent:
            score += 30
            reasoning['urgency'] = f'Urgency keywords detected: {", ".join(urgency_kws[:3])}'

        # AI confidence
        ai_result = complaint.ai_classifications.order_by('-confidence_score').first()
        if ai_result and ai_result.is_above_threshold:
            score += 15
            reasoning['ai'] = f'AI confirmed: {ai_result.predicted_class} ({ai_result.confidence_score:.1%})'

        # Description length (more detail = likely more serious)
        if len(complaint.description) > 200:
            score += 10
            reasoning['detail'] = 'Detailed description provided'

        # Determine priority
        if score >= 70:
            priority = Complaint.CRITICAL
        elif score >= 50:
            priority = Complaint.HIGH
        elif score >= 30:
            priority = Complaint.MEDIUM
        else:
            priority = Complaint.LOW

        reasoning['final_score'] = score

        PriorityPrediction.objects.update_or_create(
            complaint=complaint,
            defaults={
                'predicted_priority': priority,
                'method': 'rule_based',
                'reasoning': reasoning,
            }
        )

        # Update complaint priority
        complaint.priority = priority
        complaint.save(update_fields=['priority'])

    except Exception as e:
        logger.error(f'Priority prediction failed for complaint {complaint_id}: {e}')
