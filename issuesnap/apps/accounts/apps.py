from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'issuesnap.apps.accounts'
    label = 'accounts'
    verbose_name = 'Accounts'

    def ready(self):
        import issuesnap.apps.accounts.signals  # noqa
