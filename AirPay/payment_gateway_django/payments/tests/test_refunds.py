import uuid
from datetime import timedelta

from django.utils import timezone

from customers.models import BankAccount
from customers.tests.base import ApiTestCase
from payments.models import LedgerEntry, Refund, Transaction, Wallet
from payments.refunds import commission_to_return
from payments.services import record_successful_transaction, request_payout, settle_customer
from payments.wallet import ledger_totals

CARD = {"card_type": "credit", "network": "visa"}  # 1% commission
DEBIT = {"card_type": "debit", "network": "visa"}  # no commission


def refunds_url(txn):
    return f"/api/v1/customers/me/transactions/{txn.id}/refunds"


class RefundTestCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        self.auth = self.bearer(self.tokens()["access"])

    def collect(self, paise=100000, method="UPI", instrument=None, customer=None):
        return record_successful_transaction(customer or self.customer, amount_paise=paise, method=method, instrument=instrument)

    def refund(self, txn, body=None, key=None, auth=None):
        extra = dict(auth or self.auth)
        if key:
            extra["HTTP_IDEMPOTENCY_KEY"] = key
        return self.client.post(refunds_url(txn), body if body is not None else {}, content_type="application/json", **extra)

    def wallet(self):
        w = Wallet.objects.get(customer=self.customer)
        return w.unsettled_paise, w.settled_paise

    def account(self, number="123456789012"):
        return BankAccount.add(
            self.customer,
            account_holder_name="Acme",
            account_number=number,
            ifsc="HDFC0001234",
            bank_name="HDFC Bank",
            account_type="CURRENT",
        )

    def assert_books_balance(self):
        self.assertEqual(ledger_totals(self.customer), self.wallet())


class RefundMoneyTests(RefundTestCase):
    def test_a_full_refund_puts_the_wallet_back_where_it_was(self):
        txn = self.collect(100000)  # UPI: 1% = 10.00, so 990.00 landed
        self.assertEqual(self.wallet(), (99000, 0))

        response = self.refund(txn, {"reason": "Customer returned the item"})

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["amount"], "1000.00")
        self.assertEqual(body["commission_returned"], "10.00")
        self.assertEqual(body["net_debit"], "990.00")
        self.assertEqual(body["reason"], "Customer returned the item")
        self.assertTrue(body["reference"].startswith("AIRR"))
        self.assertEqual(body["transaction_id"], str(txn.id))
        self.assertEqual(body["transaction"]["method"], "UPI")
        self.assertEqual(self.wallet(), (0, 0))
        self.assert_books_balance()

        txn.refresh_from_db()
        self.assertEqual((txn.refunded_paise, txn.commission_refunded_paise), (100000, 1000))
        self.assertEqual(txn.refundable_paise, 0)
        # The payment itself is still a SUCCESS. The refund is a separate record.
        self.assertEqual(txn.status, "SUCCESS")

    def test_ledger_rows_show_the_refund_and_the_returned_commission(self):
        txn = self.collect(100000)
        refund_id = self.refund(txn).json()["id"]

        rows = LedgerEntry.objects.filter(reference_type="refund", reference_id=refund_id)
        got = sorted((r.kind, r.direction, r.bucket, r.amount_paise) for r in rows)
        self.assertEqual(
            got,
            [
                ("COMMISSION_REVERSAL", "CREDIT", "UNSETTLED", 1000),
                ("REFUND", "DEBIT", "UNSETTLED", 100000),
            ],
        )

    def test_a_partial_refund_returns_a_share_of_the_commission(self):
        txn = self.collect(100000)

        body = self.refund(txn, {"amount": "250.00"}).json()

        self.assertEqual((body["amount"], body["commission_returned"], body["net_debit"]), ("250.00", "2.50", "247.50"))
        self.assertEqual(self.wallet(), (99000 - 24750, 0))
        txn.refresh_from_db()
        self.assertEqual(txn.refundable_paise, 75000)
        self.assert_books_balance()

    def test_partial_refunds_add_up_to_exactly_the_commission(self):
        # 333.33 at 2% netbanking: 6.6666 -> 6.67 commission. Split in three uneven refunds.
        txn = self.collect(33333, method="NETBANKING")
        self.assertEqual(txn.commission_paise, 667)

        for amount in ("111.11", "111.11", None):  # None = whatever is left (111.11)
            response = self.refund(txn, {"amount": amount} if amount else {})
            self.assertEqual(response.status_code, 201, response.content)

        txn.refresh_from_db()
        self.assertEqual(txn.refunded_paise, 33333)
        self.assertEqual(txn.commission_refunded_paise, 667)
        self.assertEqual(self.wallet(), (0, 0))
        self.assert_books_balance()

    def test_omitting_the_amount_refunds_what_is_left(self):
        txn = self.collect(100000)
        self.refund(txn, {"amount": "400.00"})

        body = self.refund(txn).json()

        self.assertEqual(body["amount"], "600.00")
        txn.refresh_from_db()
        self.assertEqual(txn.refundable_paise, 0)
        self.assertEqual(self.wallet(), (0, 0))

    def test_a_card_with_no_commission_refunds_the_whole_amount_from_the_wallet(self):
        txn = self.collect(50000, method="CARD", instrument=DEBIT)
        self.assertEqual(self.wallet(), (50000, 0))

        body = self.refund(txn).json()

        self.assertEqual((body["commission_returned"], body["net_debit"]), ("0.00", "500.00"))
        self.assertEqual(self.wallet(), (0, 0))
        self.assertEqual(LedgerEntry.objects.filter(kind="COMMISSION_REVERSAL").count(), 0)

    def test_money_comes_out_of_unsettled_first_then_settled(self):
        first = self.collect(10000)  # 99.00 net
        settle_customer(self.customer, self.account())  # settled = 9900
        self.collect(5000)  # unsettled = 4950
        self.assertEqual(self.wallet(), (4950, 9900))

        body = self.refund(first).json()  # 100.00 refund, 1.00 commission back

        self.assertEqual(body["net_debit"], "99.00")
        # The 1.00 commission returned lands in unsettled (4950 + 100 = 5050). The 100.00
        # refund takes all 5050 of that and the other 4950 from settled.
        self.assertEqual(self.wallet(), (0, 9900 - 4950))
        self.assert_books_balance()
        kinds = LedgerEntry.objects.filter(kind="REFUND").order_by("bucket").values_list("bucket", "amount_paise")
        self.assertEqual(list(kinds), [("SETTLED", 4950), ("UNSETTLED", 5050)])

    def test_a_refund_can_be_paid_from_settled_alone(self):
        txn = self.collect(10000)
        settle_customer(self.customer, self.account())
        self.assertEqual(self.wallet(), (0, 9900))

        self.assertEqual(self.refund(txn).status_code, 201)

        self.assertEqual(self.wallet(), (0, 0))
        self.assert_books_balance()

    def test_refused_when_the_money_has_already_been_paid_out(self):
        txn = self.collect(10000)
        settle_customer(self.customer, self.account())
        request_payout(self.customer, amount_paise=9900, bank_account=self.account("987654321098"))
        self.assertEqual(self.wallet(), (0, 0))

        response = self.refund(txn)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Not enough balance", response.json()["errors"][0]["message"])
        self.assertEqual(Refund.objects.count(), 0)
        txn.refresh_from_db()
        self.assertEqual(txn.refunded_paise, 0)
        self.assert_books_balance()

    def test_cannot_refund_more_than_is_left(self):
        txn = self.collect(10000)
        self.refund(txn, {"amount": "60.00"})

        response = self.refund(txn, {"amount": "40.01"})

        self.assertEqual(response.status_code, 400)
        error = response.json()["errors"][0]
        self.assertEqual(error["field"], "amount")
        self.assertIn("Refundable: 40.00", error["message"])
        self.assertEqual(Refund.objects.count(), 1)

    def test_a_fully_refunded_payment_cannot_be_refunded_again(self):
        txn = self.collect(10000)
        self.refund(txn)

        response = self.refund(txn)

        self.assertEqual(response.status_code, 422)
        self.assertIn("already been refunded", response.json()["message"])

    def test_only_a_successful_payment_can_be_refunded(self):
        for status in ("PENDING", "FAILED", "EXPIRED", "CANCELLED"):
            txn = Transaction.objects.create(
                customer=self.customer, method="UPI", status=status, amount_paise=10000
            )
            response = self.refund(txn)
            self.assertEqual(response.status_code, 422, status)
        self.assertEqual(Refund.objects.count(), 0)

    def test_a_declined_refund_moves_no_money(self):
        txn = self.collect(500000)
        before = self.wallet()

        response = self.refund(txn, {"amount": "100.99"})  # the mock bank declines amounts ending in 99 paise

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["status"], "FAILED")
        self.assertIn("could not process", body["failure_reason"])
        self.assertEqual((body["net_debit"], body["commission_returned"], body["reference"]), ("0.00", "0.00", ""))
        self.assertEqual(self.wallet(), before)
        self.assertEqual(LedgerEntry.objects.filter(reference_type="refund").count(), 0)
        txn.refresh_from_db()
        self.assertEqual(txn.refunded_paise, 0)  # none of the refundable amount is used up
        self.assertEqual(self.refund(txn, {"amount": "100.00"}).json()["status"], "SUCCESS")


class RefundIdempotencyTests(RefundTestCase):
    def test_the_same_key_and_body_returns_the_same_refund_once(self):
        txn = self.collect(100000)

        first = self.refund(txn, {"amount": "100.00"}, key="refund-1")
        second = self.refund(txn, {"amount": "100.00"}, key="refund-1")

        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(Refund.objects.count(), 1)
        self.assertEqual(self.wallet(), (99000 - 9900, 0))

    def test_the_same_key_with_a_different_amount_is_a_conflict(self):
        txn = self.collect(100000)
        self.refund(txn, {"amount": "100.00"}, key="refund-1")

        response = self.refund(txn, {"amount": "200.00"}, key="refund-1")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Refund.objects.count(), 1)

    def test_a_bad_idempotency_key_is_rejected(self):
        txn = self.collect(10000)
        self.assertEqual(self.refund(txn, key="bad key!").status_code, 400)


class RefundValidationTests(RefundTestCase):
    def test_bad_amounts_are_rejected(self):
        txn = self.collect(10000)
        for amount in ("0", "-5.00", "abc", "1.234", ""):
            response = self.refund(txn, {"amount": amount})
            self.assertEqual(response.status_code, 400, amount)
        self.assertEqual(Refund.objects.count(), 0)

    def test_a_long_reason_is_rejected(self):
        txn = self.collect(10000)
        self.assertEqual(self.refund(txn, {"reason": "x" * 201}).status_code, 400)

    def test_commission_helper_never_returns_more_than_was_charged(self):
        txn = self.collect(333)
        for _ in range(333):
            returned = commission_to_return(txn, 1)
            txn.refunded_paise += 1
            txn.commission_refunded_paise += returned
            self.assertLessEqual(txn.commission_refunded_paise, txn.commission_paise)
        self.assertEqual(txn.commission_refunded_paise, txn.commission_paise)


class RefundAccessTests(RefundTestCase):
    def test_login_is_required(self):
        txn = self.collect(10000)
        self.assertEqual(self.client.post(refunds_url(txn), {}, content_type="application/json").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/customers/me/refunds").status_code, 401)

    def test_an_api_key_cannot_refund(self):
        txn = self.collect(10000)
        created = self.client.post(
            "/api/v1/customers/me/api-keys",
            {"name": "prod", "expires_at": (timezone.now() + timedelta(days=30)).isoformat()},
            content_type="application/json",
            **self.auth,
        )
        key = {"HTTP_X_API_KEY": created.json()["key"]}

        response = self.client.post(refunds_url(txn), {}, content_type="application/json", **key)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Refund.objects.count(), 0)

    def test_another_customers_payment_is_not_found(self):
        other = self.make_customer(email="other@acme.com")
        theirs = self.collect(10000, customer=other)

        response = self.refund(theirs)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Refund.objects.count(), 0)
        self.assertEqual(self.client.get(refunds_url(theirs), **self.auth).status_code, 404)

    def test_an_unknown_payment_is_not_found(self):
        response = self.client.post(
            f"/api/v1/customers/me/transactions/{uuid.uuid4()}/refunds", {}, content_type="application/json", **self.auth
        )
        self.assertEqual(response.status_code, 404)


class RefundReadTests(RefundTestCase):
    def test_list_and_detail_are_scoped_to_the_customer(self):
        mine = self.collect(100000)
        refund_id = self.refund(mine, {"amount": "10.00"}).json()["id"]
        other = self.make_customer(email="other@acme.com")
        theirs = self.collect(100000, customer=other)
        from payments.refunds import request_refund

        request_refund(other, theirs.id, amount_paise=1000)

        listed = self.client.get("/api/v1/customers/me/refunds", **self.auth).json()
        self.assertEqual([r["id"] for r in listed], [refund_id])

        detail = self.client.get(f"/api/v1/customers/me/refunds/{refund_id}", **self.auth)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["transaction"]["amount"], "1000.00")

        theirs_refund = Refund.objects.get(customer=other)
        self.assertEqual(
            self.client.get(f"/api/v1/customers/me/refunds/{theirs_refund.id}", **self.auth).status_code, 404
        )

    def test_a_transactions_refunds_are_listed_newest_first(self):
        txn = self.collect(100000)
        a = self.refund(txn, {"amount": "10.00"}).json()["id"]
        b = self.refund(txn, {"amount": "20.00"}).json()["id"]

        listed = self.client.get(refunds_url(txn), **self.auth).json()

        self.assertEqual([r["id"] for r in listed], [b, a])

    def test_the_transaction_shows_what_has_been_refunded(self):
        txn = self.collect(100000)
        url = f"/api/v1/customers/me/transactions/{txn.id}"

        before = self.client.get(url, **self.auth).json()
        self.assertEqual((before["refunded"], before["refundable"], before["refund_status"]), ("0.00", "1000.00", "NONE"))

        self.refund(txn, {"amount": "300.00"})
        partial = self.client.get(url, **self.auth).json()
        self.assertEqual((partial["refunded"], partial["refundable"], partial["refund_status"]), ("300.00", "700.00", "PARTIAL"))

        self.refund(txn)
        full = self.client.get(url, **self.auth).json()
        self.assertEqual((full["refunded"], full["refundable"], full["refund_status"]), ("1000.00", "0.00", "FULL"))

    def test_a_payment_that_did_not_succeed_has_nothing_refundable(self):
        txn = Transaction.objects.create(customer=self.customer, method="UPI", status="FAILED", amount_paise=10000)
        body = self.client.get(f"/api/v1/customers/me/transactions/{txn.id}", **self.auth).json()
        self.assertEqual((body["refundable"], body["refund_status"]), ("0.00", "NONE"))
