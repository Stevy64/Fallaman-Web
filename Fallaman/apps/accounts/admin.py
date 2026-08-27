from django.contrib import admin

from .models import PhoneOTP, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "display_name", "phone_verified", "is_active", "is_staff", "date_joined", "last_login")
    list_filter = ("phone_verified", "is_active", "is_staff")
    search_fields = ("phone_number", "profile__display_name", "profile__first_name")
    ordering = ("-date_joined",)
    list_select_related = ("profile",)
    readonly_fields = ("date_joined", "last_login")

    @admin.display(description="Nom")
    def display_name(self, obj):
        return obj.display_name


@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "expires_at", "attempts", "is_used", "created_at")
    readonly_fields = ("code_hash",)
    search_fields = ("phone_number",)
