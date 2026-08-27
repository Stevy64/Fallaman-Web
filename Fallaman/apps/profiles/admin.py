from django.contrib import admin

from .models import Profile, ProfileSkill, Skill


class ProfileSkillInline(admin.TabularInline):
    model = ProfileSkill
    extra = 0


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "city", "primary_profession", "looking_for", "is_public", "updated_at")
    list_filter = ("is_public", "availability", "city")
    search_fields = ("display_name", "first_name", "last_name", "looking_for", "user__phone_number")
    list_select_related = ("user", "city", "primary_profession")
    raw_id_fields = ("user",)
    inlines = [ProfileSkillInline]
    fieldsets = (
        ("Identité", {"fields": ("user", "first_name", "last_name", "display_name", "avatar", "bio")}),
        ("Recherche", {"fields": ("primary_profession", "looking_for", "years_of_experience", "availability")}),
        ("Localisation & contact", {"fields": ("city", "district", "whatsapp_number", "show_whatsapp", "is_public")}),
        ("Fichiers", {"fields": ("cv_file",)}),
    )


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    search_fields = ("name",)
