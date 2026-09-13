from django.contrib import admin

from .models import Txn


@admin.register(Txn)
class TxnAdmin(admin.ModelAdmin):
    list_display = ["id", "amount", "sender_wallet", "receiver_wallet", "is_success", "created_at"]
    list_filter = ["is_success"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at"]
