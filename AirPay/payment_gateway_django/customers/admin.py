from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from customers.models import APIKey, BankAccount, Customer


@admin.register(Customer)
class CustomerAdmin(UserAdmin):
    """Django's user admin with the customer's company fields added."""

    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "company_name", "is_active", "is_staff"]
    list_filter = ["is_active", "is_staff", "is_superuser"]
    search_fields = ["email", "first_name", "last_name", "company_name"]
    readonly_fields = ["id", "last_login", "date_joined"]

    fieldsets = (
        (None, {"fields": ("id", "username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Company", {"fields": ("company_name", "company_address")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                    "company_name",
                    "company_address",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ["prefix", "last_four", "customer", "name", "status", "expires_at", "revoked_at"]
    list_filter = ["revoked_at"]
    search_fields = ["prefix", "name", "customer__email"]
    readonly_fields = [
        "id",
        "customer",
        "prefix",
        "last_four",
        "expires_at",
        "revoked_at",
        "last_used_at",
        "created_at",
    ]
    fields = readonly_fields + ["name"]

    @admin.display(description="status")
    def status(self, key: APIKey) -> str:
        return key.status

    def has_add_permission(self, request):
        return False


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ["ifsc", "last_four", "customer", "account_holder_name", "is_default", "revoked_at"]
    list_filter = ["is_default", "account_type"]
    search_fields = ["ifsc", "last_four", "customer__email"]
    readonly_fields = [
        "id",
        "customer",
        "last_four",
        "ifsc",
        "fingerprint",
        "revoked_at",
        "created_at",
    ]
    fields = readonly_fields + ["account_holder_name", "bank_name", "account_type", "is_default"]

    def has_add_permission(self, request):
        return False
