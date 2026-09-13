from django.urls import path

from .views import WalletView

urlpatterns = [
    path("wallet/", WalletView.as_view()),
]
