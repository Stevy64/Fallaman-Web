from django.contrib import admin

from .models import Category, Profession, ProfessionAlias


class ProfessionAliasInline(admin.TabularInline):
    model = ProfessionAlias
    extra = 1


class ProfessionInline(admin.TabularInline):
    model = Profession
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProfessionInline]


@admin.register(Profession)
class ProfessionAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_popular", "is_active")
    list_filter = ("category", "is_popular", "is_active")
    search_fields = ("name", "aliases__name")
    inlines = [ProfessionAliasInline]


@admin.register(ProfessionAlias)
class ProfessionAliasAdmin(admin.ModelAdmin):
    list_display = ("name", "profession")
    search_fields = ("name", "profession__name")
