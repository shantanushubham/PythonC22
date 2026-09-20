from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from bank_account_app.models import BankAccount
from bank_txn_app.gateway import PaymentGatewayError
from bank_txn_app.models import BankTxn
from txn_app.models import Txn
from txn_app.serializers import TxnSerializer
from user_app.tests import make_user
from wallet_app.models import Wallet


def make_wallet(phone_number: str, balance: str = "0") -> Wallet:
    user = make_user(phone_number)
    return Wallet.objects.create(user=user, balance=Decimal(balance))


class TxnSerializerValidationTests(TestCase):
    """Pure validate() tests — no gateway call is ever reached here."""

    def setUp(self):
        self.wallet = make_wallet("9600000001", "1000")
        self.other_wallet = make_wallet("9600000002", "0")
        self.bank_account = BankAccount.objects.create(
            user=self.wallet.user, account_no="123456789012", ifsc_code="HDFC0001234",
            account_name="Jane Doe", bank_name="HDFC Bank",
        )

    def _serializer(self, data, user=None):
        request = SimpleNamespace(user=user or self.wallet.user)
        return TxnSerializer(data=data, context={"request": request})

    def test_requires_at_least_one_wallet(self):
        serializer = self._serializer({"amount": "10.00"})
        self.assertFalse(serializer.is_valid())

    def test_sender_and_receiver_cannot_be_the_same(self):
        serializer = self._serializer(
            {
                "amount": "10.00",
                "sender_wallet": self.wallet.id,
                "receiver_wallet": self.wallet.id,
            }
        )
        self.assertFalse(serializer.is_valid())

    def test_amount_must_be_positive(self):
        serializer = self._serializer(
            {
                "amount": "0",
                "sender_wallet": self.wallet.id,
                "receiver_wallet": self.other_wallet.id,
            }
        )
        self.assertFalse(serializer.is_valid())

    def test_insufficient_balance_rejected(self):
        serializer = self._serializer(
            {
                "amount": "9999.00",
                "sender_wallet": self.wallet.id,
                "receiver_wallet": self.other_wallet.id,
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "sender_wallet does not have sufficient balance for this transaction.",
            str(serializer.errors),
        )

    def test_bank_account_required_when_loading_money(self):
        serializer = self._serializer({"amount": "10.00", "receiver_wallet": self.wallet.id})
        self.assertFalse(serializer.is_valid())

    def test_bank_account_required_when_withdrawing_money(self):
        serializer = self._serializer({"amount": "10.00", "sender_wallet": self.wallet.id})
        self.assertFalse(serializer.is_valid())

    def test_bank_account_forbidden_for_wallet_to_wallet_transfer(self):
        serializer = self._serializer(
            {
                "amount": "10.00",
                "sender_wallet": self.wallet.id,
                "receiver_wallet": self.other_wallet.id,
                "bank_account": self.bank_account.id,
            }
        )
        self.assertFalse(serializer.is_valid())

    def test_bank_account_must_belong_to_logged_in_user(self):
        serializer = self._serializer(
            {
                "amount": "10.00",
                "sender_wallet": self.wallet.id,
                "bank_account": self.bank_account.id,
            },
            user=self.other_wallet.user,
        )
        self.assertFalse(serializer.is_valid())

    def test_valid_wallet_to_wallet_transfer_passes_validation(self):
        serializer = self._serializer(
            {
                "amount": "10.00",
                "sender_wallet": self.wallet.id,
                "receiver_wallet": self.other_wallet.id,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)


class TxnCreateWalletToWalletTests(TestCase):
    """create() for the no-bank-involved path — never calls the gateway."""

    def setUp(self):
        self.wallet = make_wallet("9600000003", "1000")
        self.other_wallet = make_wallet("9600000004", "0")

    def _create(self, amount):
        request = SimpleNamespace(user=self.wallet.user)
        serializer = TxnSerializer(
            data={
                "amount": amount,
                "sender_wallet": self.wallet.id,
                "receiver_wallet": self.other_wallet.id,
            },
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    @patch("txn_app.serializers.create_bank_transaction")
    def test_transfer_moves_balance_between_wallets_without_calling_gateway(self, mock_gateway):
        txn = self._create("100.00")

        self.wallet.refresh_from_db()
        self.other_wallet.refresh_from_db()

        self.assertTrue(txn.is_success)
        self.assertEqual(self.wallet.balance, Decimal("900.00"))
        self.assertEqual(self.other_wallet.balance, Decimal("100.00"))
        mock_gateway.assert_not_called()

    def test_transfer_does_not_create_a_bank_txn(self):
        txn = self._create("50.00")
        self.assertFalse(BankTxn.objects.filter(txn=txn).exists())


@patch("txn_app.serializers.create_bank_transaction")
class TxnCreateBankLegTests(TestCase):
    """create() for load/withdraw — always goes through the (mocked) gateway."""

    def setUp(self):
        self.wallet = make_wallet("9600000005", "1000")
        self.bank_account = BankAccount.objects.create(
            user=self.wallet.user, account_no="123456789012", ifsc_code="HDFC0001234",
            account_name="Jane Doe", bank_name="HDFC Bank",
        )

    def _create(self, data):
        request = SimpleNamespace(user=self.wallet.user)
        serializer = TxnSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_load_money_calls_gateway_with_debit_and_credits_wallet(self, mock_gateway):
        mock_gateway.return_value = {"transactionId": "txn_abc123", "status": "SUCCESS"}

        txn = self._create(
            {"amount": "500.00", "receiver_wallet": self.wallet.id, "bank_account": self.bank_account.id}
        )

        mock_gateway.assert_called_once()
        self.assertEqual(mock_gateway.call_args.kwargs["transaction_type"], "debit")

        self.wallet.refresh_from_db()
        self.assertTrue(txn.is_success)
        self.assertEqual(self.wallet.balance, Decimal("1500.00"))

        bank_txn = BankTxn.objects.get(txn=txn)
        self.assertEqual(bank_txn.status, BankTxn.Status.SUCCESS)
        self.assertEqual(bank_txn.gateway_reference_id, "txn_abc123")

    def test_withdraw_calls_gateway_with_credit_and_debits_wallet(self, mock_gateway):
        mock_gateway.return_value = {"transactionId": "txn_def456", "status": "SUCCESS"}

        txn = self._create(
            {"amount": "200.00", "sender_wallet": self.wallet.id, "bank_account": self.bank_account.id}
        )

        self.assertEqual(mock_gateway.call_args.kwargs["transaction_type"], "credit")

        self.wallet.refresh_from_db()
        self.assertTrue(txn.is_success)
        self.assertEqual(self.wallet.balance, Decimal("800.00"))

    def test_gateway_decline_does_not_move_wallet_balance(self, mock_gateway):
        mock_gateway.return_value = {
            "transactionId": "txn_failed789",
            "status": "FAILED",
            "failureReason": "Transaction declined by issuing bank",
        }

        txn = self._create(
            {"amount": "200.00", "sender_wallet": self.wallet.id, "bank_account": self.bank_account.id}
        )

        self.wallet.refresh_from_db()
        self.assertFalse(txn.is_success)
        self.assertEqual(self.wallet.balance, Decimal("1000.00"))  # unchanged

        bank_txn = BankTxn.objects.get(txn=txn)
        self.assertEqual(bank_txn.status, BankTxn.Status.FAILED)
        self.assertEqual(bank_txn.failure_reason, "Transaction declined by issuing bank")

    def test_gateway_error_prevents_txn_from_being_persisted(self, mock_gateway):
        mock_gateway.side_effect = PaymentGatewayError("Validation failed")

        request = SimpleNamespace(user=self.wallet.user)
        serializer = TxnSerializer(
            data={
                "amount": "200.00",
                "sender_wallet": self.wallet.id,
                "bank_account": self.bank_account.id,
            },
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        with self.assertRaises(Exception):
            serializer.save()

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("1000.00"))
        self.assertEqual(Txn.objects.count(), 0)
        self.assertEqual(BankTxn.objects.count(), 0)


class TxnAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.wallet = make_wallet("9600000006", "1000")
        self.other_wallet = make_wallet("9600000007", "0")

        response = self.client.post(
            "/api/auth/login/",
            {"phone_number": "9600000006", "password": "pass12345"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_unauthenticated_request_rejected(self):
        client = APIClient()
        response = client.get("/api/txns/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_wallet_to_wallet_transfer_via_api(self):
        response = self.client.post(
            "/api/txns/",
            {
                "amount": "100.00",
                "sender_wallet": self.wallet.id,
                "receiver_wallet": self.other_wallet.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_success"])

        self.wallet.refresh_from_db()
        self.other_wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("900.00"))
        self.assertEqual(self.other_wallet.balance, Decimal("100.00"))

    def test_list_only_shows_txns_involving_own_wallet(self):
        Txn.objects.create(
            amount=Decimal("10.00"), sender_wallet=self.other_wallet, receiver_wallet=None, is_success=True
        )
        self.client.post(
            "/api/txns/",
            {
                "amount": "50.00",
                "sender_wallet": self.wallet.id,
                "receiver_wallet": self.other_wallet.id,
            },
            format="json",
        )

        response = self.client.get("/api/txns/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for txn in response.data:
            self.assertTrue(
                txn["sender_wallet"] == self.wallet.id or txn["receiver_wallet"] == self.wallet.id
            )

    def test_cannot_retrieve_txn_not_involving_own_wallet(self):
        txn = Txn.objects.create(
            amount=Decimal("10.00"), sender_wallet=self.other_wallet, receiver_wallet=None, is_success=True
        )
        response = self.client.get(f"/api/txns/{txn.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_txns_are_immutable(self):
        txn = Txn.objects.create(
            amount=Decimal("10.00"), sender_wallet=self.wallet, receiver_wallet=None, is_success=True
        )
        response = self.client.patch(f"/api/txns/{txn.id}/", {"amount": "20.00"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        response = self.client.delete(f"/api/txns/{txn.id}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
