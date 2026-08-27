from django.contrib import admin

from .models import City, District, Province


class CityInline(admin.TabularInline):
    model = City
    extra = 0


class DistrictInline(admin.TabularInline):
    model = District
    extra = 0


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    inlines = [CityInline]


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "province", "is_popular")
    list_filter = ("province", "is_popular")
    search_fields = ("name",)
    inlines = [DistrictInline]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "city")
    list_filter = ("city__province",)
    search_fields = ("name", "city__name")
