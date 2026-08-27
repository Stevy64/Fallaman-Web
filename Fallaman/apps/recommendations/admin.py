from django.contrib import admin

from .models import CandidateIntroduction, RecommendationPurchase


@admin.register(RecommendationPurchase)
class RecommendationPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "kind",
        "user",
        "duration_days",
        "amount",
        "status",
        "starts_at",
        "ends_at",
        "score",
    )
    list_filter = ("kind", "status")
    search_fields = ("user__phone_number", "listing__title")
    raw_id_fields = ("user", "listing", "profile", "payment")


@admin.register(CandidateIntroduction)
class CandidateIntroductionAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "profile", "employer", "status", "created_at", "decided_at")
    list_filter = ("status",)
    raw_id_fields = ("listing", "profile", "employer")
