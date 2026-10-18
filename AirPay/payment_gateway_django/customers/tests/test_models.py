from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from uuid import UUID

from customers.models import Customer
from customers.tests.base import EMAIL, PASSWORD, ApiTestCase


class RealHasherTests(SimpleTestCase):
    """These use the settings exactly as they are, with no test shortcuts."""

    def test_bcrypt_is_the_only_hasher(self):
        self.assertEqual(
            settings.PASSWORD_HASHERS,
            ["django.contrib.auth.hashers.BCryptSHA256PasswordHasher"],
        )

    def test_passwords_are_hashed_with_bcrypt_at_cost_12(self):
        encoded = make_password(PASSWORD)

        self.assertTrue(encoded.startswith("bcrypt_sha256$$2b$12$"), encoded)
        self.assertTrue(check_password(PASSWORD, encoded))
        self.assertFalse(check_password(PASSWORD + "x", encoded))

    def test_a_weaker_hash_cannot_be_created_or_accepted(self):
        with self.assertRaises(ValueError):
            make_password("x", hasher="pbkdf2_sha256")

        pbkdf2 = "pbkdf2_sha256$1000000$somesalt$" + "A" * 43 + "="
        self.assertFalse(check_password("x", pbkdf2))


class CustomerModelTests(ApiTestCase):
    def test_the_password_is_stored_as_a_salted_bcrypt_hash(self):
        first = self.make_customer("a@acme.com")
        second = self.make_customer("b@acme.com")  # same password

        self.assertTrue(first.password.startswith("bcrypt_sha256$$2b$"))
        self.assertNotIn(PASSWORD, first.password)
        self.assertNotEqual(first.password, second.password, "each password gets its own salt")
        self.assertTrue(first.check_password(PASSWORD))
        self.assertFalse(first.check_password("wrong"))

    def test_long_passwords_are_not_cut_at_72_bytes(self):
        # Plain bcrypt ignores everything after 72 bytes. The SHA-256 variant does not.
        stem = "a" * 100
        customer = self.make_customer(password=stem + "X")

        self.assertTrue(customer.check_password(stem + "X"))
        self.assertFalse(customer.check_password(stem + "Y"))

    def test_fields(self):
        customer = self.make_customer()

        self.assertEqual(customer.first_name, "Jane")
        self.assertEqual(customer.last_name, "Doe")
        self.assertEqual(customer.company_name, "Acme Pvt Ltd")
        self.assertEqual(customer.company_address, "1 Marine Drive, Mumbai 400020")
        self.assertEqual(customer.email, EMAIL)
        self.assertEqual(customer.username, EMAIL)
        self.assertEqual(str(customer), EMAIL)

    def test_id_is_a_uuid(self):
        self.assertIsInstance(self.make_customer().id, UUID)

    def test_email_is_normalised_and_used_as_username_when_none_is_given(self):
        customer = Customer(email="  Jane.Doe@ACME.com ", first_name="J", last_name="D", company_name="A", company_address="B")
        customer.set_password(PASSWORD)
        customer.save()

        self.assertEqual(customer.email, "jane.doe@acme.com")
        self.assertEqual(customer.username, "jane.doe@acme.com")

    def test_a_given_username_is_kept(self):
        customer = self.make_customer("staff@acme.com")
        customer.username = "ops"
        customer.save()

        customer.refresh_from_db()
        self.assertEqual(customer.username, "ops")

    def test_email_is_unique(self):
        self.make_customer()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.create_user(username="x", email=EMAIL, password=PASSWORD)

    def test_the_four_profile_fields_are_required(self):
        customer = Customer(username="u", email="u@acme.com")

        with self.assertRaises(ValidationError) as caught:
            customer.full_clean(exclude=["password"])

        self.assertEqual(
            set(caught.exception.message_dict),
            {"first_name", "last_name", "company_name", "company_address"},
        )

    def test_it_is_a_regular_django_user(self):
        customer = self.make_customer()
        admin = Customer.objects.create_superuser(
            "boss", "boss@acme.com", PASSWORD,
            first_name="B", last_name="B", company_name="A", company_address="B",
        )

        self.assertTrue(customer.is_active)
        self.assertFalse(customer.is_staff or customer.is_superuser)
        self.assertTrue(admin.is_staff and admin.is_superuser)
        self.assertTrue(admin.check_password(PASSWORD))
