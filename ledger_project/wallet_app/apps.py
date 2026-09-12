from django.apps import AppConfig


class WalletAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "wallet_app"

    def ready(self) -> None:
        import wallet_app.signals  # noqa: F401
