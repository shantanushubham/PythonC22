from rest_framework import status
from rest_framework.test import APIClient

from django.test import TestCase

from user_app.models import User
from wallet_app.models import Wallet


def make_user(phone_number: str, password: str = "pass12345", **extra) -> User:
    """
    User.objects.create_user() doesn't work here — the default UserManager
    still expects a positional `username`, which this model doesn't have.
    Build the user the same way UserSignUpSerializer.create() does.
    """
    user = User(phone_number=phone_number, **extra)
    user.set_password(password)
    user.save()
    return user


class UserModelTests(TestCase):
    def test_username_field_is_phone_number(self):
        self.assertEqual(User.USERNAME_FIELD, "phone_number")
        self.assertEqual(User.REQUIRED_FIELDS, [])

    def test_password_is_hashed_not_stored_in_plaintext(self):
        user = make_user("9000000001", "supersecret")
        self.assertTrue(user.check_password("supersecret"))
        self.assertNotEqual(user.password, "supersecret")

    def test_phone_number_must_be_unique(self):
        make_user("9000000002")
        with self.assertRaises(Exception):
            make_user("9000000002")


class SignUpAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/users/"

    def test_signup_does_not_require_auth(self):
        response = self.client.post(
            self.url, {"phone_number": "9100000001", "password": "supersecret"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_signup_creates_user_and_auto_provisions_wallet(self):
        response = self.client.post(
            self.url, {"phone_number": "9100000002", "password": "supersecret"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(phone_number="9100000002")
        self.assertEqual(response.data["id"], user.id)

        wallet = Wallet.objects.get(user=user)
        self.assertEqual(wallet.balance, 0)

    def test_signup_hashes_password(self):
        self.client.post(
            self.url, {"phone_number": "9100000003", "password": "supersecret"}, format="json"
        )
        user = User.objects.get(phone_number="9100000003")
        self.assertTrue(user.check_password("supersecret"))

    def test_signup_rejects_duplicate_phone_number(self):
        self.client.post(
            self.url, {"phone_number": "9100000004", "password": "supersecret"}, format="json"
        )
        response = self.client.post(
            self.url, {"phone_number": "9100000004", "password": "anotherpass"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user("9200000001", "mypassword")

    def test_login_with_correct_credentials_returns_tokens(self):
        response = self.client.post(
            "/api/auth/login/",
            {"phone_number": "9200000001", "password": "mypassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(
            "/api/auth/login/",
            {"phone_number": "9200000001", "password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_unknown_phone_number_fails(self):
        response = self.client.post(
            "/api/auth/login/",
            {"phone_number": "9200000099", "password": "whatever"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuthenticatedAPITestCase(TestCase):
    """Base class: creates a user + wallet and logs in via the real JWT flow
    (needed because our custom auth also populates a per-request ContextVar
    that `require_current_user()` relies on — `force_authenticate` would
    bypass that and break every view under test)."""

    password = "pass12345"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user("9300000001", self.password)
        Wallet.objects.create(user=self.user)
        self.login(self.user, self.password)

    def login(self, user: User, password: str, client: APIClient | None = None) -> str:
        client = client or self.client
        response = client.post(
            "/api/auth/login/",
            {"phone_number": user.phone_number, "password": password},
            format="json",
        )
        access = response.data["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return access


class UserViewSetPermissionTests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.other_user = make_user("9300000002", self.password)
        Wallet.objects.create(user=self.other_user)

    def test_unauthenticated_request_is_rejected(self):
        client = APIClient()
        response = client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_only_sees_own_profile_in_list(self):
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [u["id"] for u in response.data]
        self.assertEqual(ids, [self.user.id])

    def test_regular_user_can_retrieve_own_profile(self):
        response = self.client.get(f"/api/users/{self.user.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.user.id)

    def test_regular_user_cannot_retrieve_other_users_profile(self):
        response = self.client.get(f"/api/users/{self.other_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_regular_user_can_update_own_profile_and_password_gets_rehashed(self):
        response = self.client.patch(
            f"/api/users/{self.user.id}/", {"password": "newpassword456"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpassword456"))

    def test_partial_update_without_password_leaves_password_untouched(self):
        response = self.client.patch(
            f"/api/users/{self.user.id}/", {"first_name": "Jane"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jane")
        self.assertTrue(self.user.check_password(self.password))

    def test_regular_user_cannot_update_other_users_profile(self):
        response = self.client.patch(
            f"/api/users/{self.other_user.id}/", {"first_name": "Hacked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_regular_user_can_delete_own_account(self):
        response = self.client.delete(f"/api/users/{self.user.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.user.id).exists())

    def test_regular_user_cannot_delete_other_users_account(self):
        response = self.client.delete(f"/api/users/{self.other_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(User.objects.filter(pk=self.other_user.id).exists())

    def test_staff_user_sees_all_users(self):
        staff = make_user("9300000003", self.password, is_staff=True)
        Wallet.objects.create(user=staff)

        staff_client = APIClient()
        self.login(staff, self.password, client=staff_client)

        response = staff_client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {u["id"] for u in response.data}
        self.assertIn(self.user.id, ids)
        self.assertIn(self.other_user.id, ids)
        self.assertIn(staff.id, ids)
