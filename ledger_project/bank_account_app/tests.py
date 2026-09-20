from django.db import IntegrityError, transaction
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from bank_account_app.models import BankAccount
from user_app.tests import make_user
from wallet_app.models import Wallet


class BankAccountModelTests(TestCase):
    def setUp(self):
        self.user = make_user("9700000001")

    def test_bank_account_creation(self):
        bank_account = BankAccount.objects.create(
            user=self.user,
            account_no="111122223333",
            ifsc_code="HDFC0001234",
            account_name="Jane Doe",
            bank_name="SBI",
        )
        self.assertEqual(bank_account.bank_name, "SBI")
        self.assertTrue(bank_account.is_active)

    def test_same_user_cannot_link_same_account_number_twice(self):
        BankAccount.objects.create(
            user=self.user, account_no="111122223333", ifsc_code="HDFC0001234",
            account_name="Jane Doe", bank_name="SBI",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BankAccount.objects.create(
                    user=self.user, account_no="111122223333", ifsc_code="ICIC0004567",
                    account_name="Jane Doe", bank_name="ICICI",
                )

    def test_different_users_can_share_the_same_account_number(self):
        other_user = make_user("9700000002")
        BankAccount.objects.create(
            user=self.user, account_no="111122223333", ifsc_code="HDFC0001234",
            account_name="Jane Doe", bank_name="SBI",
        )
        bank_account = BankAccount.objects.create(
            user=other_user, account_no="111122223333", ifsc_code="HDFC0001234",
            account_name="John Doe", bank_name="SBI",
        )
        self.assertIsNotNone(bank_account.pk)


class BankAccountAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user("9800000001")
        Wallet.objects.create(user=self.user)

        response = self.client.post(
            "/api/auth/login/",
            {"phone_number": "9800000001", "password": "pass12345"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

        self.other_user = make_user("9800000002")
        Wallet.objects.create(user=self.other_user)
        self.other_bank_account = BankAccount.objects.create(
            user=self.other_user, account_no="000011112222", ifsc_code="ICIC0004567",
            account_name="Other Person", bank_name="ICICI",
        )

    def test_unauthenticated_request_rejected(self):
        client = APIClient()
        response = client.get("/api/bank-accounts/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_bank_account_attaches_logged_in_user_automatically(self):
        response = self.client.post(
            "/api/bank-accounts/",
            {
                "account_no": "123456789012",
                "ifsc_code": "HDFC0001234",
                "account_name": "Jane Doe",
                "bank_name": "HDFC Bank",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"], self.user.id)

    def test_list_only_returns_own_bank_accounts(self):
        BankAccount.objects.create(
            user=self.user, account_no="123456789012", ifsc_code="HDFC0001234",
            account_name="Jane Doe", bank_name="HDFC Bank",
        )
        response = self.client.get("/api/bank-accounts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [ba["id"] for ba in response.data]
        self.assertNotIn(self.other_bank_account.id, ids)

    def test_cannot_retrieve_another_users_bank_account(self):
        response = self.client.get(f"/api/bank-accounts/{self.other_bank_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_bank_account_partial(self):
        bank_account = BankAccount.objects.create(
            user=self.user, account_no="123456789012", ifsc_code="HDFC0001234",
            account_name="Jane Doe", bank_name="HDFC Bank",
        )
        response = self.client.patch(
            f"/api/bank-accounts/{bank_account.id}/",
            {"account_name": "Jane A. Doe"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        bank_account.refresh_from_db()
        self.assertEqual(bank_account.account_name, "Jane A. Doe")

    def test_update_bank_account_full(self):
        bank_account = BankAccount.objects.create(
            user=self.user, account_no="123456789012", ifsc_code="HDFC0001234",
            account_name="Jane Doe", bank_name="HDFC Bank",
        )
        response = self.client.put(
            f"/api/bank-accounts/{bank_account.id}/",
            {
                "account_no": "123456789012",
                "ifsc_code": "HDFC0005678",
                "account_name": "Jane A. Doe",
                "bank_name": "HDFC Bank",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        bank_account.refresh_from_db()
        self.assertEqual(bank_account.ifsc_code, "HDFC0005678")

    def test_cannot_update_another_users_bank_account(self):
        response = self.client.patch(
            f"/api/bank-accounts/{self.other_bank_account.id}/",
            {"account_name": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_bank_account_soft_deletes_by_deactivating(self):
        bank_account = BankAccount.objects.create(
            user=self.user, account_no="123456789012", ifsc_code="HDFC0001234",
            account_name="Jane Doe", bank_name="HDFC Bank",
        )
        response = self.client.delete(f"/api/bank-accounts/{bank_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        bank_account.refresh_from_db()
        self.assertFalse(bank_account.is_active)
        self.assertTrue(BankAccount.objects.filter(pk=bank_account.id).exists())
