import os
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.urls import reverse

from customers.models import Customer
from customers.tests.base import EMAIL, PASSWORD, ApiTestCase


class AdminTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.boss = self.make_customer("boss@acme.com", is_staff=True, is_superuser=True)
        self.client.force_login(self.boss)

    def test_the_list_and_forms_open(self):
        self.make_customer()
        change = reverse("admin:customers_customer_change", args=[self.boss.id])

        for url in (
            reverse("admin:customers_customer_changelist"),
            reverse("admin:customers_customer_add"),
            change,
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_the_change_page_shows_the_hash_algorithm_but_not_the_hash(self):
        page = self.client.get(reverse("admin:customers_customer_change", args=[self.boss.id])).content.decode()

        self.assertIn("bcrypt_sha256", page)
        self.assertNotIn(self.boss.password, page)

    def test_a_customer_can_be_added_in_the_admin(self):
        response = self.client.post(
            reverse("admin:customers_customer_add"),
            {
                "username": "new@acme.com",
                "email": "New@Acme.com",
                "first_name": "New",
                "last_name": "Person",
                "company_name": "New Co",
                "company_address": "9 Road, Pune",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "usable_password": "true",
            },
        )

        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["errors"])
        customer = Customer.objects.get(username="new@acme.com")
        self.assertEqual(customer.email, "new@acme.com")
        self.assertTrue(customer.password.startswith("bcrypt_sha256$"))

    def test_createsuperuser_asks_for_the_company_fields_and_uses_bcrypt(self):
        with mock.patch.dict(os.environ, {"DJANGO_SUPERUSER_PASSWORD": PASSWORD}):
            call_command(
                "createsuperuser",
                interactive=False,
                username="root",
                email="Root@Acme.com",
                first_name="Root",
                last_name="User",
                company_name="Acme",
                company_address="HQ",
                stdout=StringIO(),
            )

        root = Customer.objects.get(username="root")
        self.assertTrue(root.is_superuser and root.is_staff)
        self.assertEqual(root.email, "root@acme.com")
        self.assertTrue(root.password.startswith("bcrypt_sha256$"))


class DocsTests(ApiTestCase):
    def schema(self):
        return self.client.get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json").json()

    def test_every_customer_and_auth_endpoint_is_documented(self):
        paths = self.schema()["paths"]

        operations = {
            (path, method): op["operationId"]
            for path, item in paths.items()
            for method, op in item.items()
        }
        self.assertEqual(operations[("/api/v1/customers", "post")], "registerCustomer")
        self.assertEqual(operations[("/api/v1/customers/me", "get")], "getCurrentCustomer")
        self.assertEqual(operations[("/api/v1/customers/me", "patch")], "updateCurrentCustomer")
        self.assertEqual(operations[("/api/v1/auth/login", "post")], "login")
        self.assertEqual(operations[("/api/v1/auth/refresh", "post")], "refreshToken")
        self.assertEqual(operations[("/api/v1/auth/logout", "post")], "logout")
        self.assertEqual(operations[("/api/v1/customers/me/api-keys", "get")], "listAPIKeys")
        self.assertEqual(operations[("/api/v1/customers/me/api-keys", "post")], "createAPIKey")
        self.assertEqual(operations[("/api/v1/customers/me/api-keys/{key_id}", "get")], "getAPIKey")
        self.assertEqual(operations[("/api/v1/customers/me/api-keys/{key_id}", "delete")], "revokeAPIKey")
        self.assertEqual(operations[("/api/v1/payments/whoami", "get")], "paymentWhoAmI")
        self.assertNotIn(("/api/v1/customers/me", "put"), operations)

    def test_login_documents_email_and_password_and_never_returns_a_password(self):
        schema = self.schema()
        request = schema["paths"]["/api/v1/auth/login"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        name = request["$ref"].split("/")[-1]

        self.assertEqual(set(schema["components"]["schemas"][name]["properties"]), {"email", "password"})
        for name, body in schema["components"]["schemas"].items():
            if "Request" not in name and name != "Register":
                self.assertNotIn("password", body.get("properties", {}), name)

    def test_jwt_and_api_key_schemes_are_on_the_right_endpoints(self):
        schema = self.schema()
        schemes = schema["components"]["securitySchemes"]

        jwt_name, api_name = None, None
        for name, scheme in schemes.items():
            if scheme.get("scheme") == "bearer":
                jwt_name = name
                self.assertEqual(scheme["bearerFormat"], "JWT")
            if scheme.get("type") == "apiKey" and scheme.get("name") == "X-API-Key":
                api_name = name
        self.assertIsNotNone(jwt_name)
        self.assertIsNotNone(api_name)

        me = schema["paths"]["/api/v1/customers/me"]["get"]
        whoami = schema["paths"]["/api/v1/payments/whoami"]["get"]
        login = schema["paths"]["/api/v1/auth/login"]["post"]
        self.assertIn({jwt_name: []}, me["security"])
        self.assertNotIn({api_name: []}, me.get("security", []))
        self.assertIn({api_name: []}, whoami["security"])
        self.assertNotIn({jwt_name: []}, whoami.get("security", []))
        self.assertNotIn(jwt_name, str(login.get("security", "")))

    def test_create_api_key_documents_the_secret_and_list_does_not(self):
        schema = self.schema()
        created = schema["paths"]["/api/v1/customers/me/api-keys"]["post"]["responses"]["201"]
        listed = schema["paths"]["/api/v1/customers/me/api-keys"]["get"]["responses"]["200"]
        created_ref = created["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
        listed_items = listed["content"]["application/json"]["schema"]
        if "$ref" in listed_items:
            listed_name = listed_items["$ref"].split("/")[-1]
            listed_props = schema["components"]["schemas"][listed_name]["properties"]
        else:
            listed_props = schema["components"]["schemas"][listed_items["items"]["$ref"].split("/")[-1]]["properties"]

        self.assertIn("key", schema["components"]["schemas"][created_ref]["properties"])
        self.assertNotIn("key", listed_props)
        self.assertNotIn("secret_hash", listed_props)
