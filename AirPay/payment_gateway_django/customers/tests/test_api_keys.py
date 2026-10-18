from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from customers.crypto import SCHEME, digest, generate, pepper, prefix_of, verify
from customers.models import APIKey
from customers.tests.base import EMAIL, ApiTestCase


def future(days=30):
    return timezone.now() + timedelta(days=days)


KEYS = "/api/v1/customers/me/api-keys"
WHOAMI = "/api/v1/payments/whoami"


class CryptoTests(SimpleTestCase):
    def test_keys_are_unique_and_well_formed(self):
        seen = set()
        for _ in range(50):
            material = generate()
            self.assertTrue(material.raw.startswith(f"{SCHEME}_"))
            self.assertEqual(prefix_of(material.raw), material.prefix)
            self.assertEqual(len(material.prefix), len("apk_") + 16)
            self.assertEqual(material.last_four, material.raw[-4:])
            self.assertEqual(len(material.secret_hash), 64)
            self.assertNotIn(material.raw, seen)
            seen.add(material.raw)

    def test_the_hash_is_keyed_and_does_not_contain_the_secret(self):
        material = generate()

        self.assertEqual(digest(material.raw), material.secret_hash)
        self.assertTrue(verify(material.raw, material.secret_hash))
        self.assertFalse(verify(material.raw[:-1] + "x", material.secret_hash))
        self.assertNotIn(material.raw, material.secret_hash)
        self.assertNotEqual(digest(material.raw), digest(generate().raw))

    def test_a_different_pepper_produces_a_different_hash(self):
        material = generate()
        original = material.secret_hash

        with override_settings(API_KEY_PEPPER="another-pepper"):
            self.assertNotEqual(digest(material.raw), original)
            self.assertFalse(verify(material.raw, original))

    def test_prefix_of_rejects_malformed_strings(self):
        good = generate().raw
        self.assertIsNotNone(prefix_of(good))
        self.assertIsNone(prefix_of(""))
        self.assertIsNone(prefix_of("Bearer abc"))
        self.assertIsNone(prefix_of(good.replace("apk_", "sk_")))
        self.assertIsNone(prefix_of("apk_nothex_secret"))

    def test_verify_is_false_when_there_is_no_row(self):
        self.assertFalse(verify(generate().raw, None))

    def test_pepper_falls_back_to_the_secret_key(self):
        with override_settings(SECRET_KEY="aaa", API_KEY_PEPPER=""):
            first = pepper()
        with override_settings(SECRET_KEY="bbb", API_KEY_PEPPER=""):
            second = pepper()
        self.assertNotEqual(first, second)
        self.assertEqual(len(first), 32)


class IssueTests(ApiTestCase):
    def test_issue_stores_the_hash_not_the_secret(self):
        customer = self.make_customer()
        key, raw = APIKey.issue(customer, name="prod", expires_at=future())

        key.refresh_from_db()
        self.assertTrue(raw.startswith("apk_"))
        self.assertNotEqual(key.secret_hash, raw)
        self.assertTrue(verify(raw, key.secret_hash))
        self.assertEqual(key.status, "active")
        self.assertEqual(customer.api_keys.count(), 1)

    def test_a_prefix_collision_is_retried(self):
        customer = self.make_customer()
        first, _ = APIKey.issue(customer, name="a", expires_at=future())
        colliding = generate()
        colliding_prefix = type(colliding)(
            raw=colliding.raw,
            prefix=first.prefix,
            last_four=colliding.last_four,
            secret_hash=colliding.secret_hash,
        )
        unique = generate()
        with mock.patch("customers.models.generate", side_effect=[colliding_prefix, unique]):
            key, raw = APIKey.issue(customer, name="b", expires_at=future())

        self.assertEqual(raw, unique.raw)
        self.assertEqual(key.prefix, unique.prefix)
        self.assertEqual(APIKey.objects.count(), 2)


class APIKeyViewTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        self.auth = self.bearer(self.tokens()["access"])

    def create(self, **body):
        payload = {"name": "Production", "expires_at": future().isoformat()}
        payload.update(body)
        return self.client.post(KEYS, payload, content_type="application/json", **self.auth)

    def test_create_returns_the_secret_once(self):
        response = self.create()

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertIn("key", body)
        self.assertTrue(body["key"].startswith(body["prefix"] + "_"))
        self.assertEqual(body["status"], "active")
        self.assertEqual(body["name"], "Production")
        self.assertEqual(body["last_four"], body["key"][-4:])
        self.assertNotIn("secret_hash", body)

    def test_the_secret_is_never_listed_or_fetched_again(self):
        created = self.create().json()
        listed = self.client.get(KEYS, **self.auth)
        fetched = self.client.get(f"{KEYS}/{created['id']}", **self.auth)

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)
        for body in (listed.json()[0], fetched.json()):
            self.assertNotIn("key", body)
            self.assertNotIn("secret_hash", body)
            self.assertNotIn(created["key"], str(body))
            self.assertEqual(body["prefix"], created["prefix"])

    def test_it_needs_a_jwt(self):
        response = self.client.post(KEYS, {"expires_at": future().isoformat()}, content_type="application/json")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], 'Bearer realm="api"')

    def test_an_api_key_cannot_create_another_api_key(self):
        raw = self.create().json()["key"]

        response = self.client.post(
            KEYS,
            {"expires_at": future().isoformat()},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Api-Key {raw}",
        )
        via_header = self.client.post(
            KEYS,
            {"expires_at": future().isoformat()},
            content_type="application/json",
            HTTP_X_API_KEY=raw,
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(via_header.status_code, 401)

    def test_a_customer_can_hold_several_keys(self):
        first = self.create(name="one").json()
        second = self.create(name="two").json()

        self.assertNotEqual(first["key"], second["key"])
        self.assertEqual(len(self.client.get(KEYS, **self.auth).json()), 2)

    def test_a_customer_cannot_see_another_customers_keys(self):
        other = self.make_customer("other@acme.com")
        APIKey.issue(other, name="secret", expires_at=future())
        mine = self.create().json()

        listed = self.client.get(KEYS, **self.auth).json()
        sneak = self.client.get(f"{KEYS}/{APIKey.objects.exclude(customer=self.customer).get().id}", **self.auth)

        self.assertEqual([row["id"] for row in listed], [mine["id"]])
        self.assertEqual(sneak.status_code, 404)

    def test_expires_at_is_required_and_must_be_in_the_future(self):
        missing = self.client.post(KEYS, {"name": "x"}, content_type="application/json", **self.auth)
        past = self.create(expires_at=(timezone.now() - timedelta(days=1)).isoformat())
        too_far = self.create(expires_at=(timezone.now() + timedelta(days=400)).isoformat())

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["errors"][0]["field"], "expires_at")
        self.assertEqual(past.status_code, 400)
        self.assertEqual(too_far.status_code, 400)

    def test_name_is_optional_and_unknown_fields_are_ignored(self):
        response = self.create(name="", secret_hash="x", prefix="apk_nope", customer=str(self.customer.id))

        self.assertEqual(response.status_code, 201)
        key = APIKey.objects.get()
        self.assertEqual(key.name, "")
        self.assertNotEqual(key.prefix, "apk_nope")
        self.assertNotEqual(key.secret_hash, "x")

    def test_the_active_key_limit(self):
        with override_settings(API_KEY_MAX_PER_CUSTOMER=2):
            self.assertEqual(self.create().status_code, 201)
            self.assertEqual(self.create().status_code, 201)
            blocked = self.create()

        self.assertEqual(blocked.status_code, 400)
        self.assertIn("maximum number", blocked.json()["errors"][0]["message"])
        self.assertEqual(APIKey.objects.count(), 2)

    def test_a_revoked_or_expired_key_does_not_count_toward_the_limit(self):
        with override_settings(API_KEY_MAX_PER_CUSTOMER=1):
            live = self.create().json()
            self.client.delete(f"{KEYS}/{live['id']}", **self.auth)
            expired, _ = APIKey.issue(self.customer, name="old", expires_at=timezone.now() - timedelta(days=1))
            self.assertEqual(expired.status, "expired")
            self.assertEqual(self.create().status_code, 201)

    def test_revoke(self):
        created = self.create().json()

        response = self.client.delete(f"{KEYS}/{created['id']}", **self.auth)
        again = self.client.delete(f"{KEYS}/{created['id']}", **self.auth)
        fetched = self.client.get(f"{KEYS}/{created['id']}", **self.auth).json()

        self.assertEqual(response.status_code, 204)
        self.assertEqual(again.status_code, 204)
        self.assertEqual(fetched["status"], "revoked")
        self.assertIsNotNone(fetched["revoked_at"])

    def test_revoke_unknown_key(self):
        response = self.client.delete(f"{KEYS}/00000000-0000-0000-0000-000000000000", **self.auth)

        self.assertEqual(response.status_code, 404)


class PaymentAuthTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        jwt = self.tokens()["access"]
        created = self.client.post(
            KEYS,
            {"name": "prod", "expires_at": future().isoformat()},
            content_type="application/json",
            **self.bearer(jwt),
        ).json()
        self.raw = created["key"]
        self.key_id = created["id"]
        self.prefix = created["prefix"]

    def whoami(self, **extra):
        return self.client.get(WHOAMI, **extra)

    def test_x_api_key_identifies_the_customer(self):
        response = self.whoami(HTTP_X_API_KEY=self.raw)

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["customer_id"], str(self.customer.id))
        self.assertEqual(body["email"], EMAIL)
        self.assertEqual(body["api_key_id"], self.key_id)
        self.assertEqual(body["api_key_prefix"], self.prefix)

    def test_authorization_api_key_scheme_also_works(self):
        response = self.whoami(HTTP_AUTHORIZATION=f"Api-Key {self.raw}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["customer_id"], str(self.customer.id))

    def test_a_jwt_cannot_call_payment_endpoints(self):
        response = self.whoami(**self.bearer(self.tokens()["access"]))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], 'Api-Key realm="api"')

    def test_missing_key(self):
        response = self.whoami()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"success": False, "message": "Authentication credentials were not provided."})

    def test_wrong_and_malformed_keys_give_the_same_answer(self):
        other, raw_other = APIKey.issue(self.make_customer("b@acme.com"), name="x", expires_at=future())
        cases = [
            self.raw[:-1] + ("A" if self.raw[-1] != "A" else "B"),
            raw_other.replace(other.prefix, self.prefix, 1),  # this customer's prefix, that customer's secret
            "not-a-key",
            "apk_ffffffffffffffff_nope",
            "Bearer " + self.raw,
        ]
        answers = [self.whoami(HTTP_X_API_KEY=value) for value in cases]

        for response in answers:
            self.assertEqual(response.status_code, 401, response.content)
            self.assertEqual(response.json(), {"success": False, "message": "Invalid API key"})

    def test_revoked_key(self):
        self.client.delete(f"{KEYS}/{self.key_id}", **self.bearer(self.tokens()["access"]))

        response = self.whoami(HTTP_X_API_KEY=self.raw)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "API key has been revoked")

    def test_expired_key(self):
        APIKey.objects.filter(pk=self.key_id).update(expires_at=timezone.now() - timedelta(seconds=1))

        response = self.whoami(HTTP_X_API_KEY=self.raw)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "API key has expired")

    def test_inactive_customer(self):
        self.customer.is_active = False
        self.customer.save()

        self.assertEqual(self.whoami(HTTP_X_API_KEY=self.raw).status_code, 401)

    def test_deleted_customer(self):
        self.customer.delete()

        self.assertEqual(self.whoami(HTTP_X_API_KEY=self.raw).status_code, 401)

    def test_last_used_at_is_recorded(self):
        self.assertIsNone(APIKey.objects.get().last_used_at)

        self.whoami(HTTP_X_API_KEY=self.raw)

        self.assertIsNotNone(APIKey.objects.get().last_used_at)

    def test_a_second_key_does_not_unlock_a_revoked_one(self):
        jwt = self.bearer(self.tokens()["access"])
        other = self.client.post(
            KEYS, {"expires_at": future().isoformat()}, content_type="application/json", **jwt
        ).json()
        self.client.delete(f"{KEYS}/{self.key_id}", **jwt)

        self.assertEqual(self.whoami(HTTP_X_API_KEY=self.raw).status_code, 401)
        self.assertEqual(self.whoami(HTTP_X_API_KEY=other["key"]).status_code, 200)

    def test_whitespace_around_the_header_is_ignored(self):
        self.assertEqual(self.whoami(HTTP_X_API_KEY="  " + self.raw + "  ").status_code, 200)
