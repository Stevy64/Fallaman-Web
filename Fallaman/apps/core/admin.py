from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "level", "category", "action", "user", "status_code", "path")
    list_filter = ("level", "category", "method")
    search_fields = ("action", "message", "path", "user__phone_number")
    readonly_fields = (
        "level",
        "category",
        "action",
        "message",
        "user",
        "path",
        "method",
        "status_code",
        "ip_address",
        "duration_ms",
        "extra",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
