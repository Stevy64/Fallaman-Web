from django.contrib import admin

from .models import PaymentTransaction, SingPayWebhookLog


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "purpose", "amount", "status", "provider", "created_at")
    list_filter = ("status", "purpose", "provider")
    search_fields = ("reference", "provider_transaction_id", "user__phone_number")
    readonly_fields = ("public_id", "created_at", "updated_at", "paid_at")


@admin.register(SingPayWebhookLog)
class SingPayWebhookLogAdmin(admin.ModelAdmin):
    list_display = ("id", "signature_valid", "processed", "created_at")
    list_filter = ("signature_valid", "processed")
