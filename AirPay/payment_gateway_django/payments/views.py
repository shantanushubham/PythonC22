"""Payment endpoints.

Transactions (card, UPI, netbanking) take an API key. The dashboard lists them
with a JWT. Balance, settlement and payouts take a JWT: the customer is moving
their own money, not charging a cardholder.
"""

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serialisers import ErrorSerializer, ValidationErrorSerializer
from customers.authentication import APIKeyAuthentication
from customers.models import BankAccount
from payments.exceptions import Conflict
from payments.idempotency import read_key
from payments.models import Payout, Refund, Settlement, Transaction
from payments.serialisers import (
    BalanceSerializer,
    CreatePayoutSerializer,
    CreateRefundSerializer,
    CreateSettlementSerializer,
    CreateTransactionSerializer,
    PayoutSerializer,
    RefundSerializer,
    SettleResponseSerializer,
    SettlementSerializer,
    TransactionSerializer,
    balance_body,
)
from payments.refunds import NotRefundable, request_refund
from payments.services import (
    IdempotencyConflict,
    create_transaction,
    refresh_transaction,
    request_payout,
    settle_customer,
)
from payments.wallet import get_or_create_wallet

BAD_REQUEST = OpenApiResponse(ValidationErrorSerializer, description="A field is missing or invalid.")
UNAUTHORIZED = OpenApiResponse(ErrorSerializer, description="The token or the credentials are not valid.")
CONFLICT = OpenApiResponse(ErrorSerializer, description="The Idempotency-Key was used for a different request.")
UNAVAILABLE = OpenApiResponse(ErrorSerializer, description="The card, UPI or netbanking service did not answer.")


class PaymentAPIView(APIView):
    """Base for every cardholder-facing payment endpoint."""

    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]


class PaymentWhoAmIBody(serializers.Serializer):
    customer_id = serializers.UUIDField()
    email = serializers.EmailField()
    company_name = serializers.CharField()
    api_key_id = serializers.UUIDField()
    api_key_prefix = serializers.CharField()
    api_key_expires_at = serializers.DateTimeField()


class PaymentWhoAmIView(PaymentAPIView):
    @extend_schema(
        operation_id="paymentWhoAmI",
        tags=["Payments"],
        summary="Identify the customer behind an API key",
        responses={
            200: PaymentWhoAmIBody,
            401: OpenApiResponse(ErrorSerializer, description="The API key is missing, invalid, revoked or expired."),
        },
    )
    def get(self, request):
        key = request.auth
        return Response(
            {
                "customer_id": request.user.id,
                "email": request.user.email,
                "company_name": request.user.company_name,
                "api_key_id": key.id,
                "api_key_prefix": key.prefix,
                "api_key_expires_at": key.expires_at,
            }
        )


def _create_transaction(request):
    serializer = CreateTransactionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        txn, replayed = create_transaction(
            request.user,
            method=data["method"],
            amount_paise=data["amount"],
            reference=data.get("reference") or "",
            description=data.get("description") or "",
            card=data.get("card"),
            payer_vpa=data.get("payer_vpa") or "",
            bank_code=data.get("bank_code") or "",
            return_url=data.get("return_url") or "",
            idempotency_key=read_key(request),
        )
    except IdempotencyConflict:
        raise Conflict
    return Response(
        TransactionSerializer(txn).data,
        status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
    )


class TransactionListCreateView(PaymentAPIView):
    @extend_schema(
        operation_id="listTransactions",
        tags=["Transactions"],
        summary="List transactions collected through AirPay",
        responses={200: TransactionSerializer(many=True), 401: UNAUTHORIZED},
    )
    def get(self, request):
        txns = Transaction.objects.filter(customer=request.user)
        return Response(TransactionSerializer(txns, many=True).data)

    @extend_schema(
        operation_id="createTransaction",
        tags=["Transactions"],
        summary="Collect a payment through AirPay",
        description=(
            "Routes the payment to the card, UPI or netbanking service. "
            "The customer's **unsettled** wallet is credited only when `status` is `SUCCESS`. "
            "Card is synchronous. UPI and netbanking start as `PENDING` — poll `GET` until they finish. "
            "A JWT is not accepted. Send `Idempotency-Key` to retry safely. "
            "The full card number and CVV are never stored or returned."
        ),
        request=CreateTransactionSerializer,
        responses={
            201: TransactionSerializer,
            200: TransactionSerializer,
            400: BAD_REQUEST,
            401: UNAUTHORIZED,
            409: CONFLICT,
            503: UNAVAILABLE,
        },
    )
    def post(self, request):
        return _create_transaction(request)


class TransactionDetailView(PaymentAPIView):
    @extend_schema(
        operation_id="getTransaction",
        tags=["Transactions"],
        summary="Get a transaction",
        description="If the transaction is still `PENDING`, AirPay asks the rail again and credits the wallet if it succeeded.",
        responses={200: TransactionSerializer, 401: UNAUTHORIZED, 404: OpenApiResponse(ErrorSerializer)},
    )
    def get(self, request, transaction_id):
        txn = get_object_or_404(Transaction, pk=transaction_id, customer=request.user)
        txn = refresh_transaction(txn)
        return Response(TransactionSerializer(txn).data)


class MyTransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="listMyTransactions",
        tags=["Transactions"],
        summary="List your AirPay transactions",
        responses={200: TransactionSerializer(many=True), 401: UNAUTHORIZED},
    )
    def get(self, request):
        txns = Transaction.objects.filter(customer=request.user)
        return Response(TransactionSerializer(txns, many=True).data)


class MyTransactionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="getMyTransaction",
        tags=["Transactions"],
        summary="Get one of your AirPay transactions",
        description="If the transaction is still `PENDING`, AirPay asks the rail again and credits the wallet if it succeeded.",
        responses={200: TransactionSerializer, 401: UNAUTHORIZED, 404: OpenApiResponse(ErrorSerializer)},
    )
    def get(self, request, transaction_id):
        txn = get_object_or_404(Transaction, pk=transaction_id, customer=request.user)
        txn = refresh_transaction(txn)
        return Response(TransactionSerializer(txn).data)


class BalanceView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BalanceSerializer

    @extend_schema(
        operation_id="getBalance",
        tags=["Balance"],
        summary="Get settled and unsettled balances",
        description="`unsettled` is money from successful AirPay transactions that cannot be paid out yet. "
        "`settled` is available for a bank-transfer payout. `total` is the sum.",
        responses={200: BalanceSerializer, 401: UNAUTHORIZED},
    )
    def get(self, request):
        return Response(balance_body(get_or_create_wallet(request.user)))


def _active_account(request, account_id) -> BankAccount:
    account = BankAccount.objects.filter(
        pk=account_id, customer=request.user, revoked_at__isnull=True
    ).first()
    if account is None:
        raise ValidationError({"bank_account_id": ["No active bank account with that id."]})
    return account


class SettleView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SettleResponseSerializer

    @extend_schema(
        operation_id="settleBalance",
        tags=["Balance"],
        summary="Settle some or all of the unsettled balance to a bank account",
        description="The customer chooses one of their active bank accounts (`bank_account_id`, from "
        "`GET /customers/me/bank-accounts`) and how much to settle (`amount`). "
        "Omit `amount` to settle the whole unsettled balance. "
        "An `amount` above the unsettled balance is rejected. "
        "In production this is a T+N job. Here the customer can trigger it.",
        request=CreateSettlementSerializer,
        responses={200: SettleResponseSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED},
    )
    def post(self, request):
        serializer = CreateSettlementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = _active_account(request, serializer.validated_data["bank_account_id"])
        wallet, moved, settlement = settle_customer(
            request.user,
            account,
            amount_paise=serializer.validated_data.get("amount"),
        )
        body = balance_body(wallet, settled_now=moved)
        body["settlement"] = SettlementSerializer(settlement).data if settlement else None
        return Response(body)


class SettlementListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="listSettlements",
        tags=["Balance"],
        summary="List your settlements",
        responses={200: SettlementSerializer(many=True), 401: UNAUTHORIZED},
    )
    def get(self, request):
        settlements = Settlement.objects.filter(customer=request.user)
        return Response(SettlementSerializer(settlements, many=True).data)


class PayoutListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="listPayouts",
        tags=["Payouts"],
        summary="List your payouts",
        responses={200: PayoutSerializer(many=True), 401: UNAUTHORIZED},
    )
    def get(self, request):
        payouts = Payout.objects.filter(customer=request.user)
        return Response(PayoutSerializer(payouts, many=True).data)

    @extend_schema(
        operation_id="requestPayout",
        tags=["Payouts"],
        summary="Pay out settled funds by bank transfer",
        description="A payout is a direct bank transfer, not an AirPay collection. "
        "Debits **settled** immediately and sends a mock NEFT/IMPS. "
        "Account numbers ending in `0000` and IFSCs starting with `FAIL` are declined "
        "and the settled balance is restored. Send `Idempotency-Key` to retry safely.",
        request=CreatePayoutSerializer,
        responses={201: PayoutSerializer, 200: PayoutSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 409: CONFLICT},
    )
    def post(self, request):
        serializer = CreatePayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = _active_account(request, serializer.validated_data["bank_account_id"])
        try:
            payout, replayed = request_payout(
                request.user,
                amount_paise=serializer.validated_data["amount"],
                bank_account=account,
                idempotency_key=read_key(request),
            )
        except IdempotencyConflict:
            raise Conflict
        return Response(
            PayoutSerializer(payout).data,
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        )


class PayoutDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="getPayout",
        tags=["Payouts"],
        summary="Get a payout",
        responses={200: PayoutSerializer, 401: UNAUTHORIZED, 404: OpenApiResponse(ErrorSerializer)},
    )
    def get(self, request, payout_id):
        payout = get_object_or_404(Payout, pk=payout_id, customer=request.user)
        return Response(PayoutSerializer(payout).data)


# --- Refunds. JWT only: the customer is sending their own money back to a payer. ---------

REFUND_NOT_FOUND = OpenApiResponse(ErrorSerializer, description="No such transaction or refund.")
NOT_REFUNDABLE = OpenApiResponse(
    ErrorSerializer, description="The payment cannot be refunded: it did not succeed, or it is already fully refunded."
)


class TransactionRefundListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="listTransactionRefunds",
        tags=["Refunds"],
        summary="List the refunds of one transaction",
        responses={200: RefundSerializer(many=True), 401: UNAUTHORIZED, 404: REFUND_NOT_FOUND},
    )
    def get(self, request, transaction_id):
        txn = get_object_or_404(Transaction, pk=transaction_id, customer=request.user)
        refunds = Refund.objects.filter(transaction=txn).select_related("transaction")
        return Response(RefundSerializer(refunds, many=True).data)

    @extend_schema(
        operation_id="createRefund",
        tags=["Refunds"],
        summary="Refund a payment, in full or in part",
        description="Sends money back to the payer for a successful payment. Omit `amount` to refund "
        "everything not yet refunded. The refund comes out of your **unsettled** balance first, then "
        "**settled**, and is refused if you no longer have the money. AirPay returns its commission in "
        "proportion to the amount refunded, so a full refund leaves your balance as it was before the "
        "payment. A JWT is required: an API key is not accepted. Send `Idempotency-Key` to retry safely. "
        "Mock bank: a refund ending in 99 paise is declined, and moves no money.",
        request=CreateRefundSerializer,
        responses={
            201: RefundSerializer,
            200: RefundSerializer,
            400: BAD_REQUEST,
            401: UNAUTHORIZED,
            404: REFUND_NOT_FOUND,
            409: CONFLICT,
            422: NOT_REFUNDABLE,
        },
    )
    def post(self, request, transaction_id):
        serializer = CreateRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refund, replayed = request_refund(
                request.user,
                transaction_id,
                amount_paise=serializer.validated_data.get("amount"),
                reason=serializer.validated_data.get("reason", ""),
                idempotency_key=read_key(request),
            )
        except Transaction.DoesNotExist:
            raise Http404
        except NotRefundable as error:
            return Response(
                {"success": False, "message": error.message}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        except IdempotencyConflict:
            raise Conflict
        return Response(
            RefundSerializer(refund).data,
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        )


class MyRefundListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="listMyRefunds",
        tags=["Refunds"],
        summary="List all your refunds",
        responses={200: RefundSerializer(many=True), 401: UNAUTHORIZED},
    )
    def get(self, request):
        refunds = Refund.objects.filter(customer=request.user).select_related("transaction")
        return Response(RefundSerializer(refunds, many=True).data)


class RefundDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="getRefund",
        tags=["Refunds"],
        summary="Get a refund",
        responses={200: RefundSerializer, 401: UNAUTHORIZED, 404: REFUND_NOT_FOUND},
    )
    def get(self, request, refund_id):
        refund = get_object_or_404(Refund.objects.select_related("transaction"), pk=refund_id, customer=request.user)
        return Response(RefundSerializer(refund).data)
