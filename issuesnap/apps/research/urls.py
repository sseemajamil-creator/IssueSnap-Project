from django.urls import path
from . import views

app_name = 'research'

urlpatterns = [
    path('', views.research_dashboard, name='dashboard'),
    path('datasets/', views.dataset_info, name='dataset_info'),
    path('models/', views.model_info, name='model_info'),
    path('models/comparison/', views.model_comparison, name='model_comparison'),
    path('experiments/', views.experiment_results, name='experiment_results'),
    path('metrics/', views.evaluation_metrics, name='evaluation_metrics'),
    path('documentation/', views.research_documentation, name='documentation'),
]
