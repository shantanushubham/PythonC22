from django.contrib import admin

from .models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "balance", "created_at", "updated_at"]
    search_fields = ["user__phone_number"]
    readonly_fields = ["created_at", "updated_at"]
