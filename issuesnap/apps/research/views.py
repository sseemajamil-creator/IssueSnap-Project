"""
IssueSnap Research Views
"""
import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import ResearchExperiment, DatasetInfo
from issuesnap.apps.ai_engine.models import ModelVersion


def research_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect('accounts:login')
        return func(request, *args, **kwargs)
    return wrapper


@research_required
def research_dashboard(request):
    experiments = ResearchExperiment.objects.all()
    models = ModelVersion.objects.all()
    datasets = DatasetInfo.objects.all()

    best_model = ModelVersion.objects.filter(
        is_trained=True, accuracy__isnull=False
    ).order_by('-accuracy').first()

    return render(request, 'research/dashboard.html', {
        'page_title': 'Research Dashboard',
        'experiments': experiments,
        'models': models,
        'datasets': datasets,
        'best_model': best_model,
        'total_experiments': experiments.count(),
        'total_models': models.count(),
    })


@research_required
def dataset_info(request):
    datasets = DatasetInfo.objects.all()

    # Recommended public datasets for civic issue detection
    recommended_datasets = [
        {
            'name': 'Road Damage Dataset (RDD2022)',
            'url': 'https://github.com/sekilab/RoadDamageDetector',
            'license': 'CC BY 4.0',
            'description': 'Large-scale road damage detection dataset with labeled images from multiple countries.',
            'classes': ['D00: Longitudinal Crack', 'D10: Transverse Crack', 'D20: Alligator Crack', 'D40: Pothole'],
            'size': '~47,000 images',
        },
        {
            'name': 'TACO (Trash Annotations in Context)',
            'url': 'http://tacodataset.org/',
            'license': 'MIT',
            'description': 'Open dataset of waste in the wild for detection and segmentation.',
            'classes': ['28 waste categories'],
            'size': '~1,500 images',
        },
        {
            'name': 'Pothole Detection Dataset (Roboflow)',
            'url': 'https://universe.roboflow.com/pothole-detection',
            'license': 'CC BY 4.0',
            'description': 'Various pothole detection datasets on Roboflow Universe.',
            'classes': ['pothole'],
            'size': 'Various sizes',
        },
    ]

    return render(request, 'research/dataset_info.html', {
        'page_title': 'Dataset Information',
        'datasets': datasets,
        'recommended_datasets': recommended_datasets,
    })


@research_required
def model_info(request):
    models = ModelVersion.objects.all().order_by('-created_at')
    active_model = ModelVersion.objects.filter(is_active=True).first()

    return render(request, 'research/model_info.html', {
        'page_title': 'Model Information',
        'models': models,
        'active_model': active_model,
    })


@research_required
def model_comparison(request):
    models = ModelVersion.objects.filter(is_trained=True).order_by('-accuracy')

    comparison_data = []
    for m in models:
        comparison_data.append({
            'name': f'{m.name} v{m.version}',
            'accuracy': m.accuracy,
            'precision': m.precision,
            'recall': m.recall,
            'f1': m.f1_score,
            'inference_ms': m.inference_time_ms,
        })

    return render(request, 'research/model_comparison.html', {
        'page_title': 'Model Comparison',
        'models': models,
        'comparison_data': json.dumps(comparison_data),
    })


@research_required
def experiment_results(request):
    experiments = ResearchExperiment.objects.filter(is_published=True).order_by('-created_at')

    return render(request, 'research/experiment_results.html', {
        'page_title': 'Experiment Results',
        'experiments': experiments,
    })


@research_required
def evaluation_metrics(request):
    best_experiment = ResearchExperiment.objects.filter(
        test_accuracy__isnull=False
    ).order_by('-test_accuracy').first()

    return render(request, 'research/evaluation_metrics.html', {
        'page_title': 'Evaluation Metrics',
        'experiment': best_experiment,
    })


@research_required
def research_documentation(request):
    return render(request, 'research/documentation.html', {
        'page_title': 'Research Documentation',
    })
