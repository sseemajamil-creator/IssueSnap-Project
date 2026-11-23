from django.urls import path
from . import views

app_name = 'ai_engine'

urlpatterns = [
    path('analyze/', views.analyze_image_api, name='analyze'),
    path('model-info/', views.model_info_api, name='model_info'),
    path('classes/', views.supported_classes_api, name='supported_classes'),
]
