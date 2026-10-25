from customers.models import BankAccount
from customers.tests.base import ApiTestCase
from payments.models import Payout, Settlement, Wallet
from payments.services import record_successful_transaction, request_payout, settle_customer
from payments.wallet import ledger_totals

NUMBER = "123456789012"


class LedgerTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()

    def account(self, number=NUMBER, ifsc="HDFC0001234", bank_name="HDFC Bank", account_type="CURRENT"):
        return BankAccount.add(
            self.customer,
            account_holder_name="Acme",
            account_number=number,
            ifsc=ifsc,
            bank_name=bank_name,
            account_type=account_type,
        )

    def test_a_new_customer_has_zero_balances(self):
        jwt = self.bearer(self.tokens()["access"])

        response = self.client.get("/api/v1/customers/me/balance", **jwt)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"currency": "INR", "unsettled": "0.00", "settled": "0.00", "total": "0.00"},
        )

    def test_a_successful_transaction_credits_unsettled(self):
        txn = record_successful_transaction(self.customer, amount_paise=150050, reference="order_1")
        wallet = Wallet.objects.get(customer=self.customer)

        self.assertEqual((wallet.unsettled_paise, wallet.settled_paise), (150050, 0))
        self.assertEqual(ledger_totals(self.customer), (150050, 0))
        self.assertEqual(txn.amount_paise, 150050)
        self.assertEqual(txn.status, "SUCCESS")
        self.assertIsNotNone(txn.credited_at)

    def test_settle_moves_unsettled_to_settled(self):
        record_successful_transaction(self.customer, amount_paise=150050)
        record_successful_transaction(self.customer, amount_paise=50)

        wallet, moved, settlement = settle_customer(self.customer, self.account())

        self.assertEqual((wallet.unsettled_paise, wallet.settled_paise, moved), (0, 150100, 150100))
        self.assertEqual(settlement.amount_paise, 150100)
        self.assertEqual(ledger_totals(self.customer), (0, 150100))

    def test_settle_a_chosen_amount(self):
        record_successful_transaction(self.customer, amount_paise=10000)
        account = self.account()

        wallet, moved, settlement = settle_customer(self.customer, account, amount_paise=2500)

        self.assertEqual((wallet.unsettled_paise, wallet.settled_paise, moved), (7500, 2500, 2500))
        self.assertEqual(settlement.bank_account_id, account.id)
        self.assertEqual(settlement.account_last_four, "9012")
        self.assertEqual(ledger_totals(self.customer), (7500, 2500))

    def test_cannot_settle_more_than_unsettled(self):
        from rest_framework.exceptions import ValidationError

        record_successful_transaction(self.customer, amount_paise=10000)

        with self.assertRaises(ValidationError):
            settle_customer(self.customer, self.account(), amount_paise=10001)
        self.assertEqual(ledger_totals(self.customer), (10000, 0))
        self.assertEqual(Settlement.objects.count(), 0)

    def test_settling_when_empty_moves_nothing(self):
        _, moved, settlement = settle_customer(self.customer, self.account())
        self.assertEqual(moved, 0)
        self.assertIsNone(settlement)

    def test_payout_debits_settled_and_failed_payout_restores_it(self):
        record_successful_transaction(self.customer, amount_paise=50000)
        good = BankAccount.add(
            self.customer,
            account_holder_name="Acme",
            account_number=NUMBER,
            ifsc="HDFC0001234",
            bank_name="HDFC Bank",
            account_type="CURRENT",
        )
        bad = BankAccount.add(
            self.customer,
            account_holder_name="Acme",
            account_number="111122220000",
            ifsc="SBIN0001111",
            bank_name="SBI",
            account_type="SAVINGS",
        )

        settle_customer(self.customer, good)
        ok, _ = request_payout(self.customer, amount_paise=20000, bank_account=good)
        fail, _ = request_payout(self.customer, amount_paise=10000, bank_account=bad)

        self.assertEqual(ok.status, Payout.Status.SUCCESS)
        self.assertTrue(ok.bank_reference.startswith("AIRP"))
        self.assertEqual(fail.status, Payout.Status.FAILED)
        self.assertIn("invalid or closed", fail.failure_reason)
        wallet = Wallet.objects.get(customer=self.customer)
        self.assertEqual((wallet.unsettled_paise, wallet.settled_paise), (0, 30000))
        self.assertEqual(ledger_totals(self.customer), (0, 30000))

    def test_cannot_payout_more_than_settled(self):
        record_successful_transaction(self.customer, amount_paise=10000)
        # still unsettled
        account = BankAccount.add(
            self.customer,
            account_holder_name="Acme",
            account_number=NUMBER,
            ifsc="HDFC0001234",
            bank_name="HDFC Bank",
            account_type="CURRENT",
        )
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            request_payout(self.customer, amount_paise=10000, bank_account=account)
        self.assertEqual(ledger_totals(self.customer), (10000, 0))
        self.assertEqual(Payout.objects.count(), 0)
