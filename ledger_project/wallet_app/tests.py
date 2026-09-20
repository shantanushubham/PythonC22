from decimal import Decimal

from rest_framework import status
from rest_framework.test import APIClient

from django.test import TestCase

from user_app.tests import make_user
from wallet_app.models import Wallet


class WalletModelTests(TestCase):
    def test_wallet_str_representation(self):
        user = make_user("9500000001")
        wallet = Wallet.objects.create(user=user, balance=Decimal("100.00"))
        text = str(wallet)
        self.assertIn(user.phone_number, text)
        self.assertIn("100.00", text)

    def test_wallet_defaults_to_zero_balance(self):
        user = make_user("9500000002")
        wallet = Wallet.objects.create(user=user)
        self.assertEqual(wallet.balance, 0)

    def test_only_one_wallet_per_user(self):
        user = make_user("9500000003")
        Wallet.objects.create(user=user)
        with self.assertRaises(Exception):
            Wallet.objects.create(user=user)


class WalletViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user("9600000001")
        self.wallet = Wallet.objects.create(user=self.user, balance=Decimal("250.00"))

        response = self.client.post(
            "/api/auth/login/",
            {"phone_number": "9600000001", "password": "pass12345"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_get_wallet_returns_own_wallet(self):
        response = self.client.get("/api/wallet/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.wallet.id)
        self.assertEqual(str(response.data["balance"]), "250.00")

    def test_unauthenticated_request_rejected(self):
        client = APIClient()
        response = client.get("/api/wallet/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wallet_endpoint_is_scoped_to_logged_in_user(self):
        other_user = make_user("9600000002")
        other_wallet = Wallet.objects.create(user=other_user, balance=Decimal("999.00"))

        response = self.client.get("/api/wallet/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response.data["id"], other_wallet.id)

    def test_wallet_endpoint_only_supports_get(self):
        response = self.client.patch("/api/wallet/", {"balance": "500.00"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        response = self.client.delete("/api/wallet/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
