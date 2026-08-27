from django.contrib import admin

from .models import Favorite, Listing, ListingImage, SearchAlert


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "listing_type", "city", "status", "published_at")
    list_filter = ("listing_type", "status", "city")
    search_fields = ("title", "description", "custom_profession", "author__phone_number")
    inlines = [ListingImageInline]
    actions = ["publish_listings", "hide_listings"]

    @admin.action(description="Publier")
    def publish_listings(self, request, queryset):
        for listing in queryset:
            listing.publish()

    @admin.action(description="Masquer")
    def hide_listings(self, request, queryset):
        queryset.update(status=Listing.Status.HIDDEN)


admin.site.register(Favorite)
admin.site.register(SearchAlert)
