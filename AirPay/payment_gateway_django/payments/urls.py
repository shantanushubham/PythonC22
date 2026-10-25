from django.urls import path

from payments.views import (
    BalanceView,
    MyTransactionDetailView,
    MyRefundListView,
    MyTransactionListView,
    PaymentWhoAmIView,
    PayoutDetailView,
    PayoutListCreateView,
    RefundDetailView,
    SettleView,
    SettlementListView,
    TransactionDetailView,
    TransactionListCreateView,
    TransactionRefundListCreateView,
)

urlpatterns = [
    path("payments/whoami", PaymentWhoAmIView.as_view(), name="payment-whoami"),
    path("transactions", TransactionListCreateView.as_view(), name="transactions"),
    path("transactions/<uuid:transaction_id>", TransactionDetailView.as_view(), name="transaction-detail"),
    path("customers/me/transactions", MyTransactionListView.as_view(), name="my-transactions"),
    path(
        "customers/me/transactions/<uuid:transaction_id>",
        MyTransactionDetailView.as_view(),
        name="my-transaction-detail",
    ),
    path(
        "customers/me/transactions/<uuid:transaction_id>/refunds",
        TransactionRefundListCreateView.as_view(),
        name="transaction-refunds",
    ),
    path("customers/me/refunds", MyRefundListView.as_view(), name="my-refunds"),
    path("customers/me/refunds/<uuid:refund_id>", RefundDetailView.as_view(), name="refund-detail"),
    path("customers/me/balance", BalanceView.as_view(), name="balance"),
    path("customers/me/settle", SettleView.as_view(), name="settle"),
    path("customers/me/settlements", SettlementListView.as_view(), name="settlements"),
    path("customers/me/payouts", PayoutListCreateView.as_view(), name="payouts"),
    path("customers/me/payouts/<uuid:payout_id>", PayoutDetailView.as_view(), name="payout-detail"),
]
