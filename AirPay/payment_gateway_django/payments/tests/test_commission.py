from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from customers.tests.base import ApiTestCase
from payments.commission import calculate, commission_on, format_rate, rate_bps_for
from payments.models import LedgerEntry, Transaction, Wallet
from payments.services import record_successful_transaction
from payments.tests.fakes import FakeRail, card_body
from payments.wallet import ledger_totals

TRANSACTIONS = "/api/v1/transactions"
BALANCE = "/api/v1/customers/me/balance"


def card(network, card_type="credit"):
    return {"network": network, "card_type": card_type, "last_four": "1111", "holder_name": "Jane"}


class CommissionRateTests(ApiTestCase):
    def test_credit_card_rates_by_network(self):
        expected = {
            "visa": 100,
            "mastercard": 100,
            "diners": 400,
            "american_express": 400,
            "rupay": 50,
        }
        for network, bps in expected.items():
            with self.subTest(network=network):
                self.assertEqual(rate_bps_for("CARD", card(network)), bps)

    def test_netbanking_and_upi_rates(self):
        self.assertEqual(rate_bps_for("NETBANKING", {"bank_code": "HDFC"}), 200)
        self.assertEqual(rate_bps_for("UPI", {"payer_vpa": "a@okaxis"}), 100)

    def test_debit_cards_and_unknown_networks_are_free(self):
        self.assertEqual(rate_bps_for("CARD", card("visa", "debit")), 0)
        self.assertEqual(rate_bps_for("CARD", card("somenew")), 0)
        self.assertEqual(rate_bps_for("CARD", {}), 0)

    def test_commission_rounds_half_up_to_the_paise(self):
        self.assertEqual(commission_on(150050, 100), 1501)  # 1500.5 paise
        self.assertEqual(commission_on(150049, 100), 1500)  # 1500.49 paise
        self.assertEqual(commission_on(10000, 50), 50)
        self.assertEqual(commission_on(100, 50), 1)  # 0.5 paise rounds up
        self.assertEqual(commission_on(99, 50), 0)  # 0.495 paise rounds down

    def test_calculate_returns_rate_and_amount(self):
        fee = calculate("CARD", card("diners"), 100000)
        self.assertEqual((fee.rate_bps, fee.amount_paise), (400, 4000))

    def test_format_rate(self):
        self.assertEqual(format_rate(100), "1.00")
        self.assertEqual(format_rate(50), "0.50")
        self.assertEqual(format_rate(400), "4.00")
        self.assertEqual(format_rate(0), "0.00")


class CommissionFlowTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        self.auth = self.bearer(self.tokens()["access"])
        created = self.client.post(
            "/api/v1/customers/me/api-keys",
            {"name": "prod", "expires_at": (timezone.now() + timedelta(days=30)).isoformat()},
            content_type="application/json",
            **self.auth,
        )
        self.api = {"HTTP_X_API_KEY": created.json()["key"]}
        self.rail = FakeRail(status="SUCCESS")
        self.upi = FakeRail(status="PENDING")
        self.nb = FakeRail(status="PENDING", redirect_url="http://localhost:8002/bank/nb_1")
        patcher = patch(
            "payments.services.get_rail",
            side_effect=lambda method: {"CARD": self.rail, "UPI": self.upi, "NETBANKING": self.nb}[method],
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def post_txn(self, body):
        return self.client.post(TRANSACTIONS, body, content_type="application/json", **self.api)

    def unsettled(self):
        return self.client.get(BALANCE, **self.auth).json()["unsettled"]

    def test_each_card_network_is_charged_its_own_rate(self):
        cases = [
            ("visa", "1.00", "10.00"),
            ("mastercard", "1.00", "10.00"),
            ("diners", "4.00", "40.00"),
            ("american_express", "4.00", "40.00"),
            ("rupay", "0.50", "5.00"),
        ]
        for network, rate, fee in cases:
            with self.subTest(network=network):
                self.rail.instrument = card(network)
                response = self.post_txn(card_body("1000.00", reference=f"o_{network}"))

                self.assertEqual(response.status_code, 201, response.content)
                body = response.json()
                self.assertEqual((body["commission_rate"], body["commission"]), (rate, fee))
                self.assertEqual(body["amount"], "1000.00")

    def test_card_commission_is_taken_from_unsettled_and_ledgered(self):
        self.rail.instrument = card("diners")

        body = self.post_txn(card_body("1000.00")).json()

        self.assertEqual(body["net_amount"], "960.00")
        self.assertEqual(self.unsettled(), "960.00")
        self.assertEqual(ledger_totals(self.customer), (96000, 0))
        entries = {e.kind: e for e in LedgerEntry.objects.filter(customer=self.customer)}
        self.assertEqual(entries["COLLECTION"].amount_paise, 100000)
        self.assertEqual(entries["COLLECTION"].direction, "CREDIT")
        self.assertEqual(entries["COMMISSION"].amount_paise, 4000)
        self.assertEqual(entries["COMMISSION"].direction, "DEBIT")
        self.assertEqual(entries["COMMISSION"].reference_id, entries["COLLECTION"].reference_id)

    def test_upi_is_charged_one_percent_when_it_succeeds(self):
        created = self.post_txn(
            {"method": "UPI", "amount": "500.00", "payer_vpa": "jane@okaxis", "reference": "u1"}
        ).json()
        self.assertEqual((created["commission"], created["net_amount"]), ("0.00", None))
        self.assertEqual(self.unsettled(), "0.00")

        self.upi.succeed_pending()
        polled = self.client.get(f"{TRANSACTIONS}/{created['id']}", **self.api).json()

        self.assertEqual((polled["commission_rate"], polled["commission"]), ("1.00", "5.00"))
        self.assertEqual(polled["net_amount"], "495.00")
        self.assertEqual(self.unsettled(), "495.00")

    def test_netbanking_is_charged_two_percent_when_it_succeeds(self):
        created = self.post_txn(
            {
                "method": "NETBANKING",
                "amount": "500.00",
                "bank_code": "HDFC",
                "return_url": "http://shop.example/back",
            }
        ).json()

        self.nb.succeed_pending()
        polled = self.client.get(f"{TRANSACTIONS}/{created['id']}", **self.api).json()

        self.assertEqual((polled["commission_rate"], polled["commission"]), ("2.00", "10.00"))
        self.assertEqual(self.unsettled(), "490.00")

    def test_a_failed_payment_pays_no_commission(self):
        self.rail.status = "FAILED"
        self.rail.failure_reason = "Insufficient funds"

        body = self.post_txn(card_body("100.00")).json()

        self.assertEqual((body["commission"], body["net_amount"]), ("0.00", None))
        self.assertEqual(ledger_totals(self.customer), (0, 0))
        self.assertFalse(LedgerEntry.objects.exists())

    def test_polling_again_does_not_charge_commission_twice(self):
        created = self.post_txn(
            {"method": "UPI", "amount": "100.00", "payer_vpa": "jane@okaxis"}
        ).json()
        self.upi.succeed_pending()
        for _ in range(3):
            self.client.get(f"{TRANSACTIONS}/{created['id']}", **self.api)

        self.assertEqual(Wallet.objects.get().unsettled_paise, 9900)
        self.assertEqual(LedgerEntry.objects.filter(kind="COMMISSION").count(), 1)

    def test_commission_is_fixed_on_the_transaction(self):
        self.rail.instrument = card("rupay")
        txn_id = self.post_txn(card_body("1000.00")).json()["id"]

        with patch.dict("payments.commission.CARD_RATES_BPS", {("credit", "rupay"): 400}):
            body = self.client.get(f"{TRANSACTIONS}/{txn_id}", **self.api).json()

        self.assertEqual((body["commission_rate"], body["commission"]), ("0.50", "5.00"))
        self.assertEqual(Transaction.objects.get(pk=txn_id).commission_paise, 500)

    def test_record_successful_transaction_applies_commission(self):
        txn = record_successful_transaction(
            self.customer, amount_paise=100000, method="UPI", instrument={"payer_vpa": "a@okaxis"}
        )

        self.assertEqual((txn.commission_rate_bps, txn.commission_paise), (100, 1000))
        self.assertEqual(ledger_totals(self.customer), (99000, 0))
