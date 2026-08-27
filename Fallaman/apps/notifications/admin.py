from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "title", "is_read", "read_at", "created_at")
    list_filter = ("kind", "is_read")
    search_fields = ("title", "body", "user__phone_number")
