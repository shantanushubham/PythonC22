from datetime import timedelta
from unittest.mock import patch

from customers.models import BankAccount
from customers.tests.base import ApiTestCase
from payments.models import Payout, Settlement, Wallet
from payments.tests.fakes import FakeRail, card_body
from payments.wallet import ledger_totals

NUMBER = "123456789012"
TRANSACTIONS = "/api/v1/transactions"
BALANCE = "/api/v1/customers/me/balance"
SETTLE = "/api/v1/customers/me/settle"
PAYOUTS = "/api/v1/customers/me/payouts"
SETTLEMENTS = "/api/v1/customers/me/settlements"
ACCOUNTS = "/api/v1/customers/me/bank-accounts"


class PaymentFlowTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        from django.utils import timezone

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
        patcher = patch("payments.services.get_rail", return_value=self.card)
        patcher.start()
        self.addCleanup(patcher.stop)

    def capture(self, amount="1500.50", **extra):
        return self.client.post(
            TRANSACTIONS,
            card_body(amount, **extra),
            content_type="application/json",
            **self.api,
        )

    def add_account(self, number=NUMBER, ifsc="HDFC0001234"):
        return self.client.post(
            ACCOUNTS,
            {
                "account_holder_name": "Acme Pvt Ltd",
                "account_number": number,
                "ifsc": ifsc,
                "bank_name": "HDFC Bank",
                "account_type": "CURRENT",
            },
            content_type="application/json",
            **self.auth,
        ).json()

    def settle(self, account_id, amount=None):
        body = {"bank_account_id": account_id}
        if amount is not None:
            body["amount"] = amount
        return self.client.post(SETTLE, body, content_type="application/json", **self.auth)

    def test_capture_needs_an_api_key_not_a_jwt(self):
        jwt_only = self.client.post(
            TRANSACTIONS, card_body("10.00"), content_type="application/json", **self.auth
        )
        self.assertEqual(jwt_only.status_code, 401)
        self.assertEqual(jwt_only["WWW-Authenticate"], 'Api-Key realm="api"')

    def test_capture_then_balance_then_settle(self):
        captured = self.capture()
        self.assertEqual(captured.status_code, 201, captured.content)
        self.assertEqual(captured.json()["amount"], "1500.50")

        before = self.client.get(BALANCE, **self.auth).json()
        self.assertEqual(before["unsettled"], "1485.49")
        self.assertEqual(before["settled"], "0.00")
        self.assertEqual(before["total"], "1485.49")

        account = self.add_account()
        settled = self.settle(account["id"])
        self.assertEqual(settled.status_code, 200, settled.content)
        self.assertEqual(settled.json()["unsettled"], "0.00")
        self.assertEqual(settled.json()["settled"], "1485.49")
        self.assertEqual(settled.json()["settled_now"], "1485.49")
        self.assertEqual(settled.json()["settlement"]["amount"], "1485.49")
        self.assertEqual(settled.json()["settlement"]["bank_account"]["id"], account["id"])
        self.assertEqual(settled.json()["settlement"]["bank_account"]["account_number_last_four"], "9012")
        self.assertNotIn(NUMBER, settled.content.decode())

    def test_settle_part_of_the_unsettled_balance(self):
        self.capture("200.00")
        account = self.add_account()

        settled = self.settle(account["id"], "75.25")

        self.assertEqual(settled.status_code, 200, settled.content)
        body = settled.json()
        self.assertEqual((body["unsettled"], body["settled"], body["settled_now"]), ("122.75", "75.25", "75.25"))
        self.assertEqual(ledger_totals(self.customer), (12275, 7525))

        rest = self.settle(account["id"]).json()
        self.assertEqual((rest["unsettled"], rest["settled"], rest["settled_now"]), ("0.00", "198.00", "122.75"))
        listed = self.client.get(SETTLEMENTS, **self.auth).json()
        self.assertEqual([item["amount"] for item in listed], ["122.75", "75.25"])

    def test_settle_more_than_unsettled_is_refused(self):
        self.capture("100.00")
        account = self.add_account()

        response = self.settle(account["id"], "99.01")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["field"], "amount")
        self.assertEqual(ledger_totals(self.customer), (9900, 0))
        self.assertEqual(Settlement.objects.count(), 0)

    def test_settle_needs_a_bank_account(self):
        self.capture("100.00")

        missing = self.client.post(SETTLE, {}, content_type="application/json", **self.auth)
        unknown = self.settle("00000000-0000-0000-0000-000000000000")

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["errors"][0]["field"], "bank_account_id")
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(ledger_totals(self.customer), (9900, 0))

    def test_settle_rejects_someone_elses_or_a_revoked_account(self):
        other = self.make_customer("other@acme.com")
        foreign = BankAccount.add(
            other,
            account_holder_name="Other",
            account_number="555566667777",
            ifsc="UTIB0001111",
            bank_name="Axis",
            account_type="SAVINGS",
        )
        self.capture("100.00")
        mine = self.add_account()
        BankAccount.objects.get(pk=mine["id"]).revoke()

        self.assertEqual(self.settle(str(foreign.id)).status_code, 400)
        self.assertEqual(self.settle(mine["id"]).status_code, 400)
        self.assertEqual(ledger_totals(self.customer), (9900, 0))

    def test_settling_with_nothing_unsettled_moves_nothing(self):
        account = self.add_account()

        response = self.settle(account["id"])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["settled_now"], "0.00")
        self.assertIsNone(response.json()["settlement"])
        self.assertEqual(self.settle(account["id"], "5.00").status_code, 400)

    def test_capture_idempotency(self):
        first = self.client.post(
            TRANSACTIONS,
            card_body("10.00", reference="a"),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="pay-1",
            **self.api,
        )
        replay = self.client.post(
            TRANSACTIONS,
            card_body("10.00", reference="a"),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="pay-1",
            **self.api,
        )
        conflict = self.client.post(
            TRANSACTIONS,
            card_body("20.00", reference="a"),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="pay-1",
            **self.api,
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.json()["id"], replay.json()["id"])
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(Wallet.objects.get().unsettled_paise, 990)

    def test_payout_happy_path(self):
        self.capture("200.00")
        account = self.add_account()
        self.settle(account["id"])

        payout = self.client.post(
            PAYOUTS,
            {"amount": "80.00", "bank_account_id": account["id"]},
            content_type="application/json",
            **self.auth,
        )

        self.assertEqual(payout.status_code, 201, payout.content)
        body = payout.json()
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["amount"], "80.00")
        self.assertTrue(body["bank_reference"].startswith("AIRP"))
        self.assertEqual(body["bank_account"]["account_number_last_four"], "9012")
        self.assertNotIn(NUMBER, payout.content.decode())

        balance = self.client.get(BALANCE, **self.auth).json()
        self.assertEqual(balance["settled"], "118.00")
        self.assertEqual(ledger_totals(self.customer), (0, 11800))

    def test_payout_from_unsettled_is_refused(self):
        self.capture("200.00")
        account = self.add_account()

        payout = self.client.post(
            PAYOUTS,
            {"amount": "80.00", "bank_account_id": account["id"]},
            content_type="application/json",
            **self.auth,
        )

        self.assertEqual(payout.status_code, 400)
        self.assertEqual(payout.json()["errors"][0]["field"], "amount")
        self.assertEqual(self.client.get(BALANCE, **self.auth).json()["unsettled"], "198.00")

    def test_failed_payout_does_not_keep_the_money(self):
        self.capture("200.00")
        account = self.add_account(number="999988880000", ifsc="SBIN0002222")
        self.settle(account["id"])

        payout = self.client.post(
            PAYOUTS,
            {"amount": "50.00", "bank_account_id": account["id"]},
            content_type="application/json",
            **self.auth,
        )

        self.assertEqual(payout.status_code, 201)
        self.assertEqual(payout.json()["status"], "FAILED")
        self.assertEqual(self.client.get(BALANCE, **self.auth).json()["settled"], "198.00")
        self.assertEqual(ledger_totals(self.customer), (0, 19800))

    def test_payout_rejects_someone_elses_account(self):
        other = self.make_customer("other@acme.com")
        foreign = BankAccount.add(
            other,
            account_holder_name="Other",
            account_number="555566667777",
            ifsc="UTIB0001111",
            bank_name="Axis",
            account_type="SAVINGS",
        )
        self.capture("200.00")
        self.settle(self.add_account()["id"])

        payout = self.client.post(
            PAYOUTS,
            {"amount": "10.00", "bank_account_id": str(foreign.id)},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(payout.status_code, 400)

    def test_payout_idempotency(self):
        self.capture("200.00")
        account = self.add_account()
        self.settle(account["id"])
        payload = {"amount": "10.00", "bank_account_id": account["id"]}

        first = self.client.post(
            PAYOUTS, payload, content_type="application/json", HTTP_IDEMPOTENCY_KEY="po-1", **self.auth
        )
        replay = self.client.post(
            PAYOUTS, payload, content_type="application/json", HTTP_IDEMPOTENCY_KEY="po-1", **self.auth
        )
        conflict = self.client.post(
            PAYOUTS,
            {"amount": "20.00", "bank_account_id": account["id"]},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="po-1",
            **self.auth,
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.json()["id"], replay.json()["id"])
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(Payout.objects.count(), 1)
        self.assertEqual(self.client.get(BALANCE, **self.auth).json()["settled"], "188.00")

    def test_payout_needs_jwt_not_an_api_key(self):
        response = self.client.post(
            PAYOUTS, {"amount": "1.00", "bank_account_id": "00000000-0000-0000-0000-000000000000"},
            content_type="application/json", **self.api
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], 'Bearer realm="api"')

    def test_min_payout(self):
        self.capture("10.00")
        account = self.add_account()
        self.settle(account["id"])

        response = self.client.post(
            PAYOUTS,
            {"amount": "0.50", "bank_account_id": account["id"]},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 400)

    def test_get_payment_and_payout(self):
        payment_id = self.capture().json()["id"]
        account = self.add_account()
        self.settle(account["id"])
        payout_id = self.client.post(
            PAYOUTS,
            {"amount": "10.00", "bank_account_id": account["id"]},
            content_type="application/json",
            **self.auth,
        ).json()["id"]

        self.assertEqual(self.client.get(f"{TRANSACTIONS}/{payment_id}", **self.api).status_code, 200)
        self.assertEqual(self.client.get(f"{PAYOUTS}/{payout_id}", **self.auth).status_code, 200)
        self.assertEqual(len(self.client.get(PAYOUTS, **self.auth).json()), 1)
