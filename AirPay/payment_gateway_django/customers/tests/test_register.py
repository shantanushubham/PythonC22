from unittest import mock

from django.db import IntegrityError

from customers.models import Customer
from customers.tests.base import EMAIL, PASSWORD, ApiTestCase


class RegisterTests(ApiTestCase):
    def test_sign_up(self):
        response = self.post("customer-register", self.registration())

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(
            set(body),
            {"id", "email", "first_name", "last_name", "company_name", "company_address", "date_joined"},
        )
        self.assertEqual(body["email"], EMAIL)
        self.assertEqual(body["company_name"], "Acme Pvt Ltd")

    def test_the_response_never_contains_the_password_or_its_hash(self):
        text = self.post("customer-register", self.registration()).content.decode()

        self.assertNotIn(PASSWORD, text)
        self.assertNotIn("bcrypt", text)
        self.assertNotIn("password", text)

    def test_the_stored_customer_uses_the_email_as_username_and_a_bcrypt_hash(self):
        self.post("customer-register", self.registration())

        customer = Customer.objects.get(email=EMAIL)
        self.assertEqual(customer.username, EMAIL)
        self.assertTrue(customer.password.startswith("bcrypt_sha256$"))
        self.assertTrue(customer.check_password(PASSWORD))

    def test_email_is_lower_cased_and_text_is_trimmed(self):
        response = self.post(
            "customer-register",
            self.registration(email="Jane.Doe@ACME.com", first_name="  Jane ", company_name=" Acme "),
        )

        self.assertEqual(response.status_code, 201)
        customer = Customer.objects.get()
        self.assertEqual((customer.email, customer.username), (EMAIL, EMAIL))
        self.assertEqual((customer.first_name, customer.company_name), ("Jane", "Acme"))

    def test_a_caller_cannot_make_themselves_an_administrator(self):
        payload = self.registration(is_staff=True, is_superuser=True, is_active=False, id="1")

        response = self.post("customer-register", payload)

        self.assertEqual(response.status_code, 201)
        customer = Customer.objects.get()
        self.assertFalse(customer.is_staff)
        self.assertFalse(customer.is_superuser)
        self.assertTrue(customer.is_active)
        self.assertNotEqual(str(customer.id), "1")

    def test_duplicate_email_is_rejected_whatever_the_case(self):
        self.make_customer()

        for email in (EMAIL, "JANE.DOE@acme.com"):
            response = self.post("customer-register", self.registration(email=email))

            self.assertEqual(response.status_code, 400)
            errors = {e["field"]: e["message"] for e in response.json()["errors"]}
            self.assertEqual(errors["email"], "A customer with this email already exists.")
        self.assertEqual(Customer.objects.count(), 1)

    def test_two_sign_ups_at_the_same_moment_give_a_400_not_a_500(self):
        # The email check passed for both, so the database's unique index decides.
        with mock.patch.object(Customer.objects, "create_user", side_effect=IntegrityError):
            response = self.post("customer-register", self.registration())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["field"], "email")

    def test_every_missing_field_is_reported_at_once(self):
        response = self.post("customer-register", {})

        self.assertEqual(response.status_code, 400)
        fields = {e["field"] for e in response.json()["errors"]}
        self.assertEqual(
            fields,
            {"email", "password", "first_name", "last_name", "company_name", "company_address"},
        )

    def test_blank_and_oversized_values(self):
        cases = {
            "first_name": ["", "   ", "a" * 151],
            "last_name": ["", "a" * 151],
            "company_name": ["", "a" * 151],
            "company_address": ["", "a" * 501],
            "email": ["", "not-an-email", "a@b", "x" * 150 + "@acme.com"],
        }
        for field, values in cases.items():
            for value in values:
                response = self.post("customer-register", self.registration(**{field: value}))

                self.assertEqual(response.status_code, 400, f"{field}={value[:20]!r}")
                self.assertIn(field, {e["field"] for e in response.json()["errors"]})
        self.assertEqual(Customer.objects.count(), 0)

    def test_weak_passwords_are_rejected(self):
        weak = {
            "too short": "Ab1!",
            "too common": "password123",
            "all digits": "93847562910384",
            "same as the email": EMAIL,
            "almost the email": "jane.doe@acme.co",
        }
        for reason, password in weak.items():
            response = self.post("customer-register", self.registration(password=password))

            self.assertEqual(response.status_code, 400, reason)
            self.assertIn("password", {e["field"] for e in response.json()["errors"]}, reason)
        self.assertEqual(Customer.objects.count(), 0)

    def test_a_weak_password_is_reported_together_with_other_mistakes(self):
        response = self.post("customer-register", self.registration(password="password", first_name=""))

        self.assertEqual({e["field"] for e in response.json()["errors"]}, {"password", "first_name"})

    def test_password_can_be_long_but_not_enormous(self):
        ok = self.post("customer-register", self.registration(password="Zq9!" * 30))
        too_long = self.post("customer-register", self.registration(email="b@acme.com", password="Zq9!" * 40))

        self.assertEqual(ok.status_code, 201)
        self.assertEqual(too_long.status_code, 400)

    def test_spaces_in_a_password_are_kept(self):
        self.post("customer-register", self.registration(password="  Corr3ct Horse Battery  "))

        self.assertTrue(Customer.objects.get().check_password("  Corr3ct Horse Battery  "))

    def test_sign_up_works_without_logging_in_and_ignores_a_bad_token(self):
        response = self.post("customer-register", self.registration(), HTTP_AUTHORIZATION="Bearer garbage")

        self.assertEqual(response.status_code, 201)
