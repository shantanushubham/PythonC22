from datetime import timedelta
from unittest import mock

import jwt
from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from customers.models import Customer
from customers.throttles import LoginRateThrottle
from customers.tests.base import EMAIL, PASSWORD, ApiTestCase


def decode(token):
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])


class LoginTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()

    def test_login_returns_an_access_and_a_refresh_token(self):
        response = self.login()

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(set(response.json()), {"access", "refresh"})

    def test_the_access_token_is_signed_short_lived_and_carries_no_secrets(self):
        tokens = self.tokens()

        payload = decode(tokens["access"])
        self.assertEqual(payload["token_type"], "access")
        self.assertEqual(payload["user_id"], str(self.customer.id))
        self.assertEqual(
            payload["exp"] - payload["iat"],
            settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds(),
        )
        self.assertEqual(set(payload), {"token_type", "exp", "iat", "jti", "user_id"})
        self.assertNotIn(PASSWORD, tokens["access"])

    def test_the_refresh_token_lives_longer_and_has_its_own_type(self):
        payload = decode(self.tokens()["refresh"])

        self.assertEqual(payload["token_type"], "refresh")
        self.assertEqual(payload["user_id"], str(self.customer.id))
        self.assertEqual(
            payload["exp"] - payload["iat"],
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds(),
        )
        self.assertGreater(
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"], settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
        )

    def test_each_login_gets_different_tokens(self):
        self.assertNotEqual(self.tokens()["refresh"], self.tokens()["refresh"])

    def test_email_is_not_case_sensitive(self):
        for email in ("JANE.DOE@ACME.COM", "  Jane.Doe@acme.com "):
            self.assertEqual(self.login(email).status_code, 200, email)

    def test_login_records_last_login(self):
        self.assertIsNone(self.customer.last_login)

        self.login()

        self.customer.refresh_from_db()
        self.assertIsNotNone(self.customer.last_login)

    def test_a_wrong_password_and_an_unknown_email_give_the_same_answer(self):
        wrong_password = self.login(password="Wr0ng-password-here")
        unknown_email = self.login(email="nobody@acme.com")

        for response in (wrong_password, unknown_email):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(wrong_password.json(), unknown_email.json())
        self.assertEqual(
            wrong_password.json(),
            {"success": False, "message": "No active account found with the given credentials"},
        )

    def test_a_failed_login_does_not_record_last_login(self):
        self.login(password="Wr0ng-password-here")

        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.last_login)

    def test_an_inactive_customer_cannot_log_in(self):
        self.customer.is_active = False
        self.customer.save()

        self.assertEqual(self.login().status_code, 401)

    def test_missing_fields_are_a_400(self):
        response = self.post("auth-login", {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual({e["field"] for e in response.json()["errors"]}, {"email", "password"})

    def test_the_username_field_is_not_the_way_in(self):
        response = self.post("auth-login", {"username": EMAIL, "password": PASSWORD})

        self.assertEqual(response.status_code, 400)

    def test_login_is_rate_limited_per_address(self):
        with mock.patch.dict(LoginRateThrottle.THROTTLE_RATES, {"login": "3/minute"}):
            statuses = [self.login(password="Wr0ng-password-here").status_code for _ in range(5)]

        self.assertEqual(statuses, [401, 401, 401, 429, 429])

    def test_the_rate_limit_answer_has_retry_after_and_the_standard_shape(self):
        with mock.patch.dict(LoginRateThrottle.THROTTLE_RATES, {"login": "1/minute"}):
            self.login()
            response = self.login()

        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertFalse(response.json()["success"])


class RefreshTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        self.tokens_ = self.tokens()

    def refresh(self, token):
        return self.post("auth-refresh", {"refresh": token})

    def test_refresh_returns_a_new_pair(self):
        response = self.refresh(self.tokens_["refresh"])

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(set(body), {"access", "refresh"})
        self.assertNotEqual(body["refresh"], self.tokens_["refresh"])
        self.assertEqual(decode(body["access"])["user_id"], str(self.customer.id))

    def test_the_new_access_token_works(self):
        body = self.refresh(self.tokens_["refresh"]).json()

        response = self.client.get("/api/v1/customers/me", **self.bearer(body["access"]))

        self.assertEqual(response.status_code, 200)

    def test_a_refresh_token_works_only_once(self):
        first = self.refresh(self.tokens_["refresh"])
        replay = self.refresh(self.tokens_["refresh"])

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(replay.json(), {"success": False, "message": "Token is blacklisted"})

    def test_the_rotated_refresh_token_keeps_working(self):
        newer = self.refresh(self.tokens_["refresh"]).json()["refresh"]

        self.assertEqual(self.refresh(newer).status_code, 200)

    def test_an_access_token_is_not_accepted_as_a_refresh_token(self):
        response = self.refresh(self.tokens_["access"])

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["success"])

    def test_garbage_and_missing_tokens(self):
        garbage = self.refresh("not.a.token")
        missing = self.post("auth-refresh", {})

        self.assertEqual(garbage.status_code, 401)
        self.assertEqual(garbage.json(), {"success": False, "message": "Token is invalid"})
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["errors"][0]["field"], "refresh")

    def test_an_expired_refresh_token_is_rejected(self):
        token = RefreshToken.for_user(self.customer)
        token.set_exp(from_time=timezone.now() - timedelta(days=30), lifetime=timedelta(days=1))

        self.assertEqual(self.refresh(str(token)).status_code, 401)

    def test_a_deactivated_customer_cannot_refresh(self):
        self.customer.is_active = False
        self.customer.save()

        self.assertEqual(self.refresh(self.tokens_["refresh"]).status_code, 401)

    def test_a_deleted_customer_cannot_refresh(self):
        Customer.objects.all().delete()

        self.assertEqual(self.refresh(self.tokens_["refresh"]).status_code, 401)


class LogoutTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.make_customer()
        self.tokens_ = self.tokens()

    def test_logout_revokes_the_refresh_token(self):
        response = self.post("auth-logout", {"refresh": self.tokens_["refresh"]})
        after = self.post("auth-refresh", {"refresh": self.tokens_["refresh"]})

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(after.status_code, 401)

    def test_logout_does_not_touch_other_sessions(self):
        other = self.tokens()["refresh"]

        self.post("auth-logout", {"refresh": self.tokens_["refresh"]})

        self.assertEqual(self.post("auth-refresh", {"refresh": other}).status_code, 200)

    def test_logging_out_twice_is_refused(self):
        self.post("auth-logout", {"refresh": self.tokens_["refresh"]})

        again = self.post("auth-logout", {"refresh": self.tokens_["refresh"]})

        self.assertEqual(again.status_code, 401)

    def test_bad_input(self):
        self.assertEqual(self.post("auth-logout", {}).status_code, 400)
        self.assertEqual(self.post("auth-logout", {"refresh": "nope"}).status_code, 401)
        self.assertEqual(self.post("auth-logout", {"refresh": self.tokens_["access"]}).status_code, 401)

    def test_an_issued_access_token_works_until_it_expires(self):
        # Access tokens are stateless. This is why they are short lived.
        self.post("auth-logout", {"refresh": self.tokens_["refresh"]})

        response = self.client.get("/api/v1/customers/me", **self.bearer(self.tokens_["access"]))

        self.assertEqual(response.status_code, 200)


class AccessTokenSecurityTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()

    def me(self, token):
        return self.client.get("/api/v1/customers/me", **self.bearer(token))

    def claims(self, **override):
        claims = {
            "token_type": "access",
            "exp": int((timezone.now() + timedelta(minutes=5)).timestamp()),
            "iat": int(timezone.now().timestamp()),
            "jti": "forged",
            "user_id": str(self.customer.id),
        }
        claims.update(override)
        return claims

    def test_a_token_signed_with_another_key_is_rejected(self):
        forged = jwt.encode(self.claims(), "an-attackers-own-secret-key-0123456789", algorithm="HS256")

        self.assertEqual(self.me(forged).status_code, 401)

    def test_an_unsigned_token_is_rejected(self):
        unsigned = jwt.encode(self.claims(), key=None, algorithm="none")

        self.assertEqual(self.me(unsigned).status_code, 401)

    def test_a_correctly_signed_token_is_accepted(self):
        # Proves the two tests above fail because of the signature, nothing else.
        genuine = jwt.encode(self.claims(), settings.SECRET_KEY, algorithm="HS256")

        self.assertEqual(self.me(genuine).status_code, 200)

    def test_an_expired_access_token_is_rejected(self):
        token = AccessToken.for_user(self.customer)
        token.set_exp(from_time=timezone.now() - timedelta(hours=2), lifetime=timedelta(minutes=1))

        response = self.me(str(token))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"success": False, "message": "Given token not valid for any token type"})

    def test_a_refresh_token_cannot_be_used_to_call_the_api(self):
        self.assertEqual(self.me(self.tokens()["refresh"]).status_code, 401)

    def test_a_token_for_a_deactivated_customer_stops_working_at_once(self):
        access = self.tokens()["access"]
        self.customer.is_active = False
        self.customer.save()

        self.assertEqual(self.me(access).status_code, 401)

    def test_a_token_for_a_deleted_customer_is_rejected(self):
        access = self.tokens()["access"]
        Customer.objects.all().delete()

        self.assertEqual(self.me(access).status_code, 401)

    def test_a_malformed_authorization_header(self):
        for header in ("Bearer", "Bearer a b", "Token abc", "Basic abc"):
            response = self.client.get("/api/v1/customers/me", HTTP_AUTHORIZATION=header)

            self.assertEqual(response.status_code, 401, header)
