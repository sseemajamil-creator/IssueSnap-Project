from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'issuesnap.apps.pages'
    label = 'pages'
    verbose_name = 'Pages'
