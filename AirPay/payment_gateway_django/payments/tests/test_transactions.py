from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from customers.tests.base import ApiTestCase
from payments.models import Transaction, Wallet
from payments.tests.fakes import FakeRail, card_body
from payments.wallet import ledger_totals

TRANSACTIONS = "/api/v1/transactions"
MINE = "/api/v1/customers/me/transactions"
BALANCE = "/api/v1/customers/me/balance"


class TransactionTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        jwt = self.tokens()["access"]
        self.auth = self.bearer(jwt)
        created = self.client.post(
            "/api/v1/customers/me/api-keys",
            {"name": "prod", "expires_at": (timezone.now() + timedelta(days=30)).isoformat()},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.api = {"HTTP_X_API_KEY": created.json()["key"]}
        self.card = FakeRail(status="SUCCESS")
        self.upi = FakeRail(status="PENDING")
        self.nb = FakeRail(status="PENDING", redirect_url="http://localhost:8002/bank/nb_1")
        patcher = patch("payments.services.get_rail", side_effect=self._rail)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _rail(self, method):
        return {"CARD": self.card, "UPI": self.upi, "NETBANKING": self.nb}[method]

    def post_txn(self, body, **extra):
        return self.client.post(TRANSACTIONS, body, content_type="application/json", **self.api, **extra)

    def test_create_needs_an_api_key_not_a_jwt(self):
        response = self.client.post(
            TRANSACTIONS, card_body(), content_type="application/json", **self.auth
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], 'Api-Key realm="api"')

    def test_successful_card_credits_unsettled(self):
        response = self.post_txn(card_body())

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["method"], "CARD")
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["amount"], "1500.50")
        self.assertTrue(body["credited"])
        self.assertEqual(body["instrument"]["last_four"], "1111")
        self.assertNotIn("4111111111111111", response.content.decode())
        self.assertNotIn("123", str(body["instrument"]))

        balance = self.client.get(BALANCE, **self.auth).json()
        self.assertEqual(body["commission"], "15.01")
        self.assertEqual(body["commission_rate"], "1.00")
        self.assertEqual(body["net_amount"], "1485.49")
        self.assertEqual(balance["unsettled"], "1485.49")
        self.assertEqual(balance["settled"], "0.00")
        self.assertEqual(ledger_totals(self.customer), (148549, 0))

    def test_failed_card_does_not_credit(self):
        self.card.status = "FAILED"
        self.card.failure_reason = "Insufficient funds"

        response = self.post_txn(card_body())

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["status"], "FAILED")
        self.assertFalse(body["credited"])
        self.assertEqual(body["failure_reason"], "Insufficient funds")
        self.assertEqual(self.client.get(BALANCE, **self.auth).json()["unsettled"], "0.00")
        self.assertEqual(Transaction.objects.count(), 1)

    def test_pending_upi_does_not_credit_until_success(self):
        created = self.post_txn(
            {
                "method": "UPI",
                "amount": "200.00",
                "payer_vpa": "jane.doe@okaxis",
                "reference": "order_upi",
            }
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["status"], "PENDING")
        self.assertFalse(created.json()["credited"])
        self.assertEqual(self.client.get(BALANCE, **self.auth).json()["unsettled"], "0.00")

        self.upi.succeed_pending()
        polled = self.client.get(f"{TRANSACTIONS}/{created.json()['id']}", **self.api)
        self.assertEqual(polled.status_code, 200)
        self.assertEqual(polled.json()["status"], "SUCCESS")
        self.assertTrue(polled.json()["credited"])
        self.assertEqual(self.client.get(BALANCE, **self.auth).json()["unsettled"], "198.00")

        again = self.client.get(f"{TRANSACTIONS}/{created.json()['id']}", **self.api)
        self.assertEqual(again.json()["status"], "SUCCESS")
        self.assertEqual(Wallet.objects.get().unsettled_paise, 19800)
        self.assertEqual(ledger_totals(self.customer), (19800, 0))

    def test_failed_upi_never_credits(self):
        created = self.post_txn(
            {"method": "UPI", "amount": "50.00", "payer_vpa": "declined@okaxis"}
        )
        self.upi.fail_pending()
        polled = self.client.get(f"{TRANSACTIONS}/{created.json()['id']}", **self.api)

        self.assertEqual(polled.json()["status"], "FAILED")
        self.assertFalse(polled.json()["credited"])
        self.assertEqual(self.client.get(BALANCE, **self.auth).json()["total"], "0.00")

    def test_netbanking_returns_a_redirect_while_pending(self):
        created = self.post_txn(
            {
                "method": "NETBANKING",
                "amount": "10.00",
                "bank_code": "HDFC",
                "return_url": "https://shop.example.com/return",
            }
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["status"], "PENDING")
        self.assertTrue(created.json()["redirect_url"].startswith("http://localhost:8002/bank/"))
        self.assertFalse(created.json()["credited"])

    def test_rail_down_creates_nothing(self):
        self.card.unavailable = True
        response = self.post_txn(card_body())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Wallet.objects.count(), 0)

    def test_rail_validation_is_returned_as_400(self):
        self.card.validation_errors = [{"field": "card.number", "message": "card number failed the Luhn check"}]
        response = self.post_txn(card_body())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["field"], "card.number")
        self.assertEqual(Transaction.objects.count(), 0)

    def test_idempotency(self):
        first = self.post_txn(card_body("10.00"), HTTP_IDEMPOTENCY_KEY="pay-1")
        replay = self.post_txn(card_body("10.00"), HTTP_IDEMPOTENCY_KEY="pay-1")
        conflict = self.post_txn(card_body("20.00"), HTTP_IDEMPOTENCY_KEY="pay-1")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.json()["id"], replay.json()["id"])
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(Wallet.objects.get().unsettled_paise, 990)
        self.assertEqual(len([call for call in self.card.calls if call[0] == "create"]), 1)

    def test_method_fields_are_required(self):
        missing_card = self.post_txn({"method": "CARD", "amount": "10.00"})
        missing_vpa = self.post_txn({"method": "UPI", "amount": "10.00"})
        missing_bank = self.post_txn({"method": "NETBANKING", "amount": "10.00", "return_url": "https://shop.example.com/r"})

        self.assertEqual(missing_card.status_code, 400)
        self.assertEqual(missing_card.json()["errors"][0]["field"], "card")
        self.assertEqual(missing_vpa.status_code, 400)
        self.assertEqual(missing_bank.status_code, 400)

    def test_dashboard_lists_transactions_with_a_jwt(self):
        created = self.post_txn(card_body("25.00"))
        listed = self.client.get(MINE, **self.auth)
        detail = self.client.get(f"{MINE}/{created.json()['id']}", **self.auth)

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(listed.json()[0]["status"], "SUCCESS")
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json()["credited"])

        with_key = self.client.get(MINE, **self.api)
        self.assertEqual(with_key.status_code, 401)

    def test_list_with_api_key(self):
        self.post_txn(card_body("5.00"))
        response = self.client.get(TRANSACTIONS, **self.api)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
