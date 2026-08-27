from django.contrib import admin

from .models import BlockedUser, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reason", "listing", "reporter", "status", "created_at")
    list_filter = ("reason", "status")
    actions = ["resolve"]

    @admin.action(description="Marquer comme traité")
    def resolve(self, request, queryset):
        queryset.update(status=Report.Status.RESOLVED)


admin.site.register(BlockedUser)
