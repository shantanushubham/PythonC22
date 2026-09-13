from django.contrib import admin

from .models import BankAccount


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "account_name", "account_no", "ifsc_code", "bank_name", "is_active"]
    search_fields = ["user__phone_number", "account_no", "ifsc_code"]
    list_filter = ["is_active", "bank_name"]
    readonly_fields = ["created_at", "updated_at"]
