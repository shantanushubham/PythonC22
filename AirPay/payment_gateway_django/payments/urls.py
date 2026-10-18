from django.urls import path

from payments.views import PaymentWhoAmIView

urlpatterns = [
    path("payments/whoami", PaymentWhoAmIView.as_view(), name="payment-whoami"),
]
