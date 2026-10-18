import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.db import OperationalError
from django.http import Http404
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import path
from rest_framework import exceptions, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import flatten_validation_errors

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# --- Health -----------------------------------------------------------------------------


class HealthTests(TestCase):
    def test_healthy(self):
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "airpay-gateway", "database": "ok"},
        )

    def test_reports_503_when_the_database_is_down(self):
        broken = mock.MagicMock()
        broken.cursor.side_effect = OperationalError("connection refused")

        with mock.patch("core.views.connection", broken):
            response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertEqual(response.json()["database"], "unavailable")

    def test_needs_no_login(self):
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)


# --- The error shape --------------------------------------------------------------------


class UnknownRouteTests(TestCase):
    def test_unknown_route_is_json(self):
        response = self.client.get("/api/v1/nope")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {"success": False, "message": "Route GET /api/v1/nope not found"},
        )

    def test_wrong_method_uses_the_standard_shape(self):
        response = self.client.post("/api/v1/health", data={}, content_type="application/json")

        self.assertEqual(response.status_code, 405)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIn("not allowed", body["message"])
        self.assertEqual(response["Allow"], "GET, HEAD, OPTIONS")


class ItemSerializer(serializers.Serializer):
    qty = serializers.IntegerField(min_value=1)


class OrderSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    items = ItemSerializer(many=True)

    def validate(self, attrs):
        if attrs["amount"] == 13:
            raise serializers.ValidationError("Unlucky amount.")
        return attrs


class OrderView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = OrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"ok": True})


class ProtectedView(APIView):
    """Uses the project defaults on purpose: nobody is allowed in."""

    def get(self, request):
        return Response({"secret": 1})


class _Raises(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    error: Exception

    def get(self, request):
        raise self.error


class ThrottledView(_Raises):
    error = exceptions.Throttled(wait=7)


class MissingView(_Raises):
    error = Http404()


class TeapotView(_Raises):
    error = exceptions.APIException("I am a teapot")


class BoomView(_Raises):
    error = RuntimeError("secret internal detail")


urlpatterns = [
    path("order", OrderView.as_view()),
    path("protected", ProtectedView.as_view()),
    path("throttled", ThrottledView.as_view()),
    path("missing", MissingView.as_view()),
    path("teapot", TeapotView.as_view()),
    path("boom", BoomView.as_view()),
]
handler404 = "core.exceptions.not_found"
handler500 = "core.exceptions.server_error"


@override_settings(ROOT_URLCONF=__name__)
class ErrorShapeTests(SimpleTestCase):
    def post_order(self, payload):
        return self.client.post("/order", payload, content_type="application/json")

    def test_validation_errors_are_flat_and_field_named(self):
        response = self.post_order({"amount": "abc", "items": [{"qty": 1}, {"qty": 0}]})

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["message"], "Validation failed")
        by_field = {e["field"]: e["message"] for e in body["errors"]}
        self.assertEqual(set(by_field), {"amount", "items.1.qty"})
        self.assertEqual(by_field["amount"], "A valid number is required.")

    def test_missing_fields_are_all_reported(self):
        body = self.post_order({}).json()

        self.assertEqual({e["field"] for e in body["errors"]}, {"amount", "items"})

    def test_object_level_errors_use_non_field_errors(self):
        body = self.post_order({"amount": "13", "items": []}).json()

        self.assertIn({"field": "non_field_errors", "message": "Unlucky amount."}, body["errors"])

    def test_malformed_json_is_a_400(self):
        response = self.client.post("/order", "{nope", content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertNotIn("errors", response.json())

    def test_only_json_is_accepted(self):
        response = self.client.post("/order", "a=1", content_type="application/x-www-form-urlencoded")

        self.assertEqual(response.status_code, 415)
        self.assertFalse(response.json()["success"])

    def test_closed_by_default(self):
        response = self.client.get("/protected")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], 'Bearer realm="api"')
        self.assertEqual(response.json()["success"], False)
        self.assertIn("Authentication credentials", response.json()["message"])

    def test_throttled_keeps_the_retry_after_header(self):
        response = self.client.get("/throttled")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "7")
        self.assertEqual(response.json(), {"success": False, "message": "Too many requests. Try again later."})

    def test_http404_inside_a_view(self):
        response = self.client.get("/missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"success": False, "message": "Not found"})

    def test_other_api_exceptions_keep_their_status_and_message(self):
        response = self.client.get("/teapot")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"success": False, "message": "I am a teapot"})

    def test_an_unexpected_error_is_a_json_500_that_leaks_nothing(self):
        self.client.raise_request_exception = False
        with self.assertLogs("django.request", level="ERROR"):
            response = self.client.get("/boom")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"success": False, "message": "Internal server error"})
        self.assertNotIn("secret internal detail", response.content.decode())


class FlattenTests(SimpleTestCase):
    def test_nested_structures(self):
        detail = {
            "customer": {"email": ["Bad email."]},
            "items": [{}, {"qty": ["Too small.", "Not a number."]}],
            "non_field_errors": ["Nope."],
        }

        flat = flatten_validation_errors(detail)

        self.assertEqual(
            flat,
            [
                {"field": "customer.email", "message": "Bad email."},
                {"field": "items.1.qty", "message": "Too small."},
                {"field": "items.1.qty", "message": "Not a number."},
                {"field": "non_field_errors", "message": "Nope."},
            ],
        )

    def test_a_bare_list_belongs_to_the_body(self):
        self.assertEqual(
            flatten_validation_errors(["Expected an object."]),
            [{"field": "body", "message": "Expected an object."}],
        )


# --- API documentation -------------------------------------------------------------------


class DocsTests(TestCase):
    def test_schema_endpoint(self):
        response = self.client.get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")

        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertTrue(schema["openapi"].startswith("3."))
        self.assertEqual(schema["paths"]["/api/v1/health"]["get"]["operationId"], "getHealth")

    def test_schema_generates_without_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            call_command("spectacular", "--fail-on-warn", "--file", os.path.join(tmp, "schema.yml"))

    def test_swagger_ui(self):
        response = self.client.get("/api/docs/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("swagger", response.content.decode().lower())


# --- Settings -----------------------------------------------------------------------------


class SettingsSafetyTests(SimpleTestCase):
    """A production start must not quietly use the development secret."""

    def load_settings(self, **env):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
        clean.update({"DB_ENGINE": "sqlite", **env})
        return subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            cwd=PROJECT_ROOT,
            env=clean,
            capture_output=True,
            text=True,
        )

    def test_debug_off_requires_a_secret_key(self):
        result = self.load_settings(DJANGO_DEBUG="0", DJANGO_ALLOWED_HOSTS="pay.example.com")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_debug_off_requires_allowed_hosts(self):
        result = self.load_settings(DJANGO_DEBUG="0", DJANGO_SECRET_KEY="x" * 50)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_debug_off_with_both_set_loads(self):
        result = self.load_settings(
            DJANGO_DEBUG="0", DJANGO_SECRET_KEY="x" * 50, DJANGO_ALLOWED_HOSTS="pay.example.com"
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_db_engine_is_rejected(self):
        result = self.load_settings(DB_ENGINE="mongo")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DB_ENGINE", result.stderr)
