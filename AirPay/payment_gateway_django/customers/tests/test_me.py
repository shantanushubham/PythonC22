from customers.models import Customer
from customers.tests.base import EMAIL, PASSWORD, ApiTestCase

ME = "/api/v1/customers/me"


class CurrentCustomerTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        self.auth = self.bearer(self.tokens()["access"])

    def patch(self, data, **extra):
        return self.client.patch(ME, data, content_type="application/json", **(extra or self.auth))

    def test_get_me(self):
        response = self.client.get(ME, **self.auth)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], str(self.customer.id))
        self.assertEqual(body["email"], EMAIL)
        self.assertEqual(body["company_name"], "Acme Pvt Ltd")
        self.assertNotIn("password", body)

    def test_it_needs_a_token(self):
        response = self.client.get(ME)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], 'Bearer realm="api"')
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {"success": False, "message": "Authentication credentials were not provided."},
        )

    def test_a_customer_only_ever_sees_themselves(self):
        self.make_customer("other@acme.com", company_name="Other Co")

        self.assertEqual(self.client.get(ME, **self.auth).json()["company_name"], "Acme Pvt Ltd")

    def test_update_the_profile(self):
        response = self.patch({"first_name": "Janet", "company_name": "Acme Global", "company_address": "5 Park St, Kolkata"})

        self.assertEqual(response.status_code, 200, response.content)
        self.customer.refresh_from_db()
        self.assertEqual(
            (self.customer.first_name, self.customer.last_name, self.customer.company_name, self.customer.company_address),
            ("Janet", "Doe", "Acme Global", "5 Park St, Kolkata"),
        )
        self.assertEqual(response.json()["first_name"], "Janet")

    def test_fields_that_must_not_change_are_ignored(self):
        original_id = self.customer.id
        original_hash = self.customer.password

        response = self.patch(
            {
                "email": "hacker@evil.com",
                "username": "hacker",
                "password": "N3w-Password-Value",
                "is_staff": True,
                "is_superuser": True,
                "id": "00000000-0000-0000-0000-000000000000",
                "first_name": "Janet",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, EMAIL)
        self.assertEqual(self.customer.username, EMAIL)
        self.assertEqual(self.customer.password, original_hash)
        self.assertFalse(self.customer.is_staff or self.customer.is_superuser)
        self.assertEqual(self.customer.id, original_id)
        self.assertEqual(self.customer.first_name, "Janet")

    def test_the_old_password_still_works_after_a_patch(self):
        self.patch({"password": "N3w-Password-Value"})

        self.assertEqual(self.login(password=PASSWORD).status_code, 200)

    def test_invalid_values_are_rejected(self):
        for field, value in {"first_name": "", "last_name": "x" * 151, "company_address": "y" * 501}.items():
            response = self.patch({field: value})

            self.assertEqual(response.status_code, 400, field)
            self.assertEqual(response.json()["errors"][0]["field"], field)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Jane")

    def test_put_and_delete_are_not_allowed(self):
        put = self.client.put(ME, {}, content_type="application/json", **self.auth)
        delete = self.client.delete(ME, **self.auth)

        self.assertEqual(put.status_code, 405)
        self.assertEqual(delete.status_code, 405)
        self.assertEqual(Customer.objects.count(), 1)

    def test_patch_without_a_token_changes_nothing(self):
        response = self.client.patch(ME, {"first_name": "X"}, content_type="application/json")

        self.assertEqual(response.status_code, 401)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Jane")


class EndToEndTests(ApiTestCase):
    def test_sign_up_log_in_use_the_api_refresh_and_log_out(self):
        signed_up = self.post("customer-register", self.registration())
        self.assertEqual(signed_up.status_code, 201)

        tokens = self.login().json()
        me = self.client.get(ME, **self.bearer(tokens["access"]))
        self.assertEqual(me.json()["id"], signed_up.json()["id"])

        rotated = self.post("auth-refresh", {"refresh": tokens["refresh"]}).json()
        self.assertEqual(self.client.get(ME, **self.bearer(rotated["access"])).status_code, 200)

        self.assertEqual(self.post("auth-logout", {"refresh": rotated["refresh"]}).status_code, 204)
        self.assertEqual(self.post("auth-refresh", {"refresh": rotated["refresh"]}).status_code, 401)
