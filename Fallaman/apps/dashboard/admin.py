from django.contrib import admin

from .models import StaffBroadcast


@admin.register(StaffBroadcast)
class StaffBroadcastAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "audience", "recipient", "recipient_count", "created_at")
    list_filter = ("audience",)
    search_fields = ("title", "body", "recipient__phone_number", "recipient__profile__display_name")
    raw_id_fields = ("recipient",)
