from django.contrib import admin

from payments.models import LedgerEntry, Payout, Refund, Transaction, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["customer", "unsettled_paise", "settled_paise", "updated_at"]
    search_fields = ["customer__email"]
    readonly_fields = ["customer", "unsettled_paise", "settled_paise", "updated_at"]

    def has_add_permission(self, request):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["created_at", "customer", "kind", "direction", "bucket", "amount_paise"]
    list_filter = ["kind", "bucket", "direction"]
    search_fields = ["customer__email"]
    readonly_fields = [field.name for field in LedgerEntry._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "method", "status", "amount_paise", "commission_paise", "refunded_paise", "credited_at", "created_at"]
    list_filter = ["method", "status"]
    search_fields = ["customer__email", "reference", "rail_transaction_id"]
    readonly_fields = [field.name for field in Transaction._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "amount_paise", "status", "ifsc", "account_last_four", "created_at"]
    list_filter = ["status"]
    search_fields = ["customer__email", "bank_reference", "ifsc"]
    readonly_fields = [field.name for field in Payout._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "transaction", "amount_paise", "commission_returned_paise", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["customer__email", "reference", "transaction__reference"]
    readonly_fields = [field.name for field in Refund._meta.fields]

    def has_add_permission(self, request):
        return False
