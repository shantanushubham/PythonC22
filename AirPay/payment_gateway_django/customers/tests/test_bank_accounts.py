from django.test import override_settings

from customers.accounts import decrypt_account_number
from customers.models import BankAccount
from customers.tests.base import EMAIL, ApiTestCase

ACCOUNTS = "/api/v1/customers/me/bank-accounts"
NUMBER = "123456789012"


class BankAccountTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        self.auth = self.bearer(self.tokens()["access"])

    def add(self, **body):
        payload = {
            "account_holder_name": "Acme Pvt Ltd",
            "account_number": NUMBER,
            "ifsc": "HDFC0001234",
            "bank_name": "HDFC Bank",
            "account_type": "CURRENT",
        }
        payload.update(body)
        return self.client.post(ACCOUNTS, payload, content_type="application/json", **self.auth)

    def test_add_and_list(self):
        response = self.add()

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["account_number_last_four"], "9012")
        self.assertEqual(body["ifsc"], "HDFC0001234")
        self.assertTrue(body["is_default"])
        self.assertNotIn("account_number", body)
        self.assertNotIn(NUMBER, response.content.decode())

        listed = self.client.get(ACCOUNTS, **self.auth)
        self.assertEqual(len(listed.json()), 1)

    def test_the_full_number_is_encrypted_in_the_database(self):
        self.add()
        account = BankAccount.objects.get()

        self.assertEqual(account.last_four, "9012")
        self.assertNotEqual(account.account_number_encrypted, NUMBER)
        self.assertNotIn(NUMBER, account.account_number_encrypted)
        self.assertEqual(decrypt_account_number(account.account_number_encrypted), NUMBER)

    def test_ifsc_is_uppercased_and_spaces_stripped(self):
        response = self.add(ifsc=" hdfc0001234 ", account_number=" 123456789012 ")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["ifsc"], "HDFC0001234")

    def test_the_first_account_is_the_default(self):
        first = self.add().json()
        second = self.add(account_number="998877665544", ifsc="SBIN0001234", is_default=False).json()

        self.assertTrue(first["is_default"])
        self.assertFalse(second["is_default"])

    def test_setting_a_new_default_unsets_the_old_one(self):
        first = self.add().json()
        second = self.add(account_number="998877665544", ifsc="SBIN0001234", is_default=True).json()

        self.assertTrue(second["is_default"])
        fetched = self.client.get(f"{ACCOUNTS}/{first['id']}", **self.auth).json()
        self.assertFalse(fetched["is_default"])

    def test_duplicate_account_is_rejected(self):
        self.add()
        again = self.add()

        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.json()["errors"][0]["field"], "account_number")

    def test_validation(self):
        cases = {
            "account_number": ["123", "abcd567890", "1" * 19],
            "ifsc": ["HDFC", "hdfc000", "FAIL0", "12340001234"],
            "account_type": ["WALLET"],
            "account_holder_name": [""],
        }
        for field, values in cases.items():
            for value in values:
                response = self.add(**{field: value})
                self.assertEqual(response.status_code, 400, f"{field}={value}")
                self.assertIn(field, {e["field"] for e in response.json()["errors"]})
        self.assertEqual(BankAccount.objects.count(), 0)

    def test_limit(self):
        with override_settings(BANK_ACCOUNT_MAX_PER_CUSTOMER=1):
            self.assertEqual(self.add().status_code, 201)
            blocked = self.add(account_number="998877665544", ifsc="SBIN0001234")
        self.assertEqual(blocked.status_code, 400)

    def test_another_customer_cannot_see_or_change_an_account(self):
        account_id = self.add().json()["id"]
        other = self.make_customer("other@acme.com")
        other_auth = self.bearer(self.tokens("other@acme.com")["access"])

        self.assertEqual(self.client.get(ACCOUNTS, **other_auth).json(), [])
        self.assertEqual(self.client.get(f"{ACCOUNTS}/{account_id}", **other_auth).status_code, 404)
        self.assertEqual(self.client.delete(f"{ACCOUNTS}/{account_id}", **other_auth).status_code, 404)

    def test_needs_a_jwt_not_an_api_key(self):
        self.assertEqual(self.client.get(ACCOUNTS).status_code, 401)

    def test_remove_promotes_another_default(self):
        first = self.add().json()
        second = self.add(account_number="998877665544", ifsc="SBIN0001234").json()

        self.assertEqual(self.client.delete(f"{ACCOUNTS}/{first['id']}", **self.auth).status_code, 204)
        remaining = self.client.get(ACCOUNTS, **self.auth).json()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["id"], second["id"])
        self.assertTrue(remaining[0]["is_default"])
        self.assertTrue(BankAccount.objects.get(pk=first["id"]).revoked_at)

    def test_patch_holder_name(self):
        account_id = self.add().json()["id"]

        response = self.client.patch(
            f"{ACCOUNTS}/{account_id}",
            {"account_holder_name": "Acme Global"},
            content_type="application/json",
            **self.auth,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["account_holder_name"], "Acme Global")
        self.assertEqual(response.json()["account_number_last_four"], "9012")
