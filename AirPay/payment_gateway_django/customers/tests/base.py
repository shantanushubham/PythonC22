from django.contrib.auth.hashers import BCryptSHA256PasswordHasher
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from customers.models import Customer

PASSWORD = "Corr3ct-Horse-Battery"
EMAIL = "jane.doe@acme.com"


class FastBCryptSHA256PasswordHasher(BCryptSHA256PasswordHasher):
    """The real hasher with the cost turned down from 12 to 4, so tests run quickly.

    Everything else is identical: same algorithm name, same salting, same SHA-256 step.
    """

    rounds = 4


@override_settings(PASSWORD_HASHERS=["customers.tests.base.FastBCryptSHA256PasswordHasher"])
class ApiTestCase(TestCase):
    def setUp(self):
        cache.clear()  # throttle counters live in the cache

    # --- helpers ---

    def post(self, url_name_or_path, data=None, **extra):
        url = reverse(url_name_or_path) if not url_name_or_path.startswith("/") else url_name_or_path
        return self.client.post(url, data if data is not None else {}, content_type="application/json", **extra)

    def make_customer(self, email=EMAIL, password=PASSWORD, **extra):
        defaults = {
            "first_name": "Jane",
            "last_name": "Doe",
            "company_name": "Acme Pvt Ltd",
            "company_address": "1 Marine Drive, Mumbai 400020",
        }
        defaults.update(extra)
        return Customer.objects.create_user(username=email, email=email, password=password, **defaults)

    def login(self, email=EMAIL, password=PASSWORD):
        return self.post("auth-login", {"email": email, "password": password})

    def tokens(self, customer_email=EMAIL):
        response = self.login(customer_email)
        assert response.status_code == 200, response.content
        return response.json()

    @staticmethod
    def bearer(token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def registration(self, **overrides):
        payload = {
            "email": EMAIL,
            "password": PASSWORD,
            "first_name": "Jane",
            "last_name": "Doe",
            "company_name": "Acme Pvt Ltd",
            "company_address": "1 Marine Drive, Mumbai 400020",
        }
        payload.update(overrides)
        return payload
