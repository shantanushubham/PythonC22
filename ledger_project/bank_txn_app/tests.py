from decimal import Decimal
from unittest.mock import patch

import requests
from django.db import IntegrityError, transaction
from django.test import TestCase

from bank_account_app.models import BankAccount
from bank_txn_app.gateway import PaymentGatewayError, create_bank_transaction
from bank_txn_app.models import BankTxn
from txn_app.models import Txn
from user_app.tests import make_user
from wallet_app.models import Wallet


class BankTxnModelTests(TestCase):
    def setUp(self):
        self.user = make_user("9700000001")
        self.wallet = Wallet.objects.create(user=self.user, balance=Decimal("100.00"))
        self.bank_account = BankAccount.objects.create(
            user=self.user, account_no="123456789012", ifsc_code="HDFC0001234",
            account_name="Jane Doe", bank_name="HDFC Bank",
        )
        self.txn = Txn.objects.create(
            amount=Decimal("50.00"), receiver_wallet=self.wallet, is_success=True
        )

    def test_bank_txn_defaults_to_pending(self):
        bank_txn = BankTxn.objects.create(txn=self.txn, bank_account=self.bank_account)
        self.assertEqual(bank_txn.status, BankTxn.Status.PENDING)

    def test_bank_txn_str_representation(self):
        bank_txn = BankTxn.objects.create(
            txn=self.txn, bank_account=self.bank_account, status=BankTxn.Status.SUCCESS
        )
        text = str(bank_txn)
        self.assertIn(str(self.txn.id), text)
        self.assertIn("SUCCESS", text)

    def test_only_one_bank_txn_per_txn(self):
        BankTxn.objects.create(txn=self.txn, bank_account=self.bank_account)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BankTxn.objects.create(txn=self.txn, bank_account=self.bank_account)

    def test_bank_account_cannot_be_deleted_while_referenced(self):
        BankTxn.objects.create(txn=self.txn, bank_account=self.bank_account)
        with self.assertRaises(Exception):
            with transaction.atomic():
                self.bank_account.delete()


class PaymentGatewayClientTests(TestCase):
    @patch("bank_txn_app.gateway.requests.post")
    def test_successful_call_returns_data(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "success": True,
            "data": {"transactionId": "txn_abc", "status": "SUCCESS"},
        }

        data = create_bank_transaction(
            account_no="123456789012", ifsc_code="HDFC0001234", account_name="Jane Doe",
            bank_name="HDFC Bank", transaction_type="credit", amount=Decimal("100.00"),
        )

        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["transactionId"], "txn_abc")

    @patch("bank_txn_app.gateway.requests.post")
    def test_bank_decline_402_is_returned_not_raised(self, mock_post):
        mock_post.return_value.status_code = 402
        mock_post.return_value.json.return_value = {
            "success": False,
            "data": {
                "transactionId": "txn_def",
                "status": "FAILED",
                "failureReason": "Bank server timeout",
            },
        }

        data = create_bank_transaction(
            account_no="123456789012", ifsc_code="HDFC0001234", account_name="Jane Doe",
            bank_name="HDFC Bank", transaction_type="debit", amount=Decimal("50.00"),
        )

        self.assertEqual(data["status"], "FAILED")
        self.assertEqual(data["failureReason"], "Bank server timeout")

    @patch("bank_txn_app.gateway.requests.post")
    def test_400_validation_error_raises_gateway_error(self, mock_post):
        mock_post.return_value.status_code = 400
        mock_post.return_value.json.return_value = {
            "success": False,
            "message": "Validation failed",
        }

        with self.assertRaises(PaymentGatewayError):
            create_bank_transaction(
                account_no="123456789012", ifsc_code="BADIFSC", account_name="Jane Doe",
                bank_name="HDFC Bank", transaction_type="debit", amount=Decimal("50.00"),
            )

    @patch("bank_txn_app.gateway.requests.post")
    def test_network_failure_raises_gateway_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("boom")

        with self.assertRaises(PaymentGatewayError):
            create_bank_transaction(
                account_no="123456789012", ifsc_code="HDFC0001234", account_name="Jane Doe",
                bank_name="HDFC Bank", transaction_type="debit", amount=Decimal("50.00"),
            )

    @patch("bank_txn_app.gateway.requests.post")
    def test_missing_data_key_raises_gateway_error(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"success": True}

        with self.assertRaises(PaymentGatewayError):
            create_bank_transaction(
                account_no="123456789012", ifsc_code="HDFC0001234", account_name="Jane Doe",
                bank_name="HDFC Bank", transaction_type="debit", amount=Decimal("50.00"),
            )

    @patch("bank_txn_app.gateway.requests.post")
    def test_non_json_response_raises_gateway_error(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.side_effect = ValueError("not json")

        with self.assertRaises(PaymentGatewayError):
            create_bank_transaction(
                account_no="123456789012", ifsc_code="HDFC0001234", account_name="Jane Doe",
                bank_name="HDFC Bank", transaction_type="debit", amount=Decimal("50.00"),
            )
