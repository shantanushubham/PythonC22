from django.urls import path

from customers.views import (
    APIKeyDetailView,
    APIKeyListCreateView,
    BankAccountDetailView,
    BankAccountListCreateView,
    CurrentCustomerView,
    LoginView,
    LogoutView,
    RefreshView,
    RegisterView,
)

urlpatterns = [
    path("customers", RegisterView.as_view(), name="customer-register"),
    path("customers/me", CurrentCustomerView.as_view(), name="customer-me"),
    path("customers/me/api-keys", APIKeyListCreateView.as_view(), name="api-keys"),
    path("customers/me/api-keys/<uuid:key_id>", APIKeyDetailView.as_view(), name="api-key-detail"),
    path("customers/me/bank-accounts", BankAccountListCreateView.as_view(), name="bank-accounts"),
    path(
        "customers/me/bank-accounts/<uuid:account_id>",
        BankAccountDetailView.as_view(),
        name="bank-account-detail",
    ),
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/refresh", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
]
