from django.conf import settings

from apps.notifications.models import Notification


def fallaman(request):
    unread = 0
    unread_messages = 0
    favorite_ids = set()
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        from apps.messaging.models import Message
        from apps.listings.models import Favorite

        unread_messages = (
            Message.objects.filter(
                conversation__user_low=request.user,
                is_read=False,
            )
            .exclude(sender=request.user)
            .count()
            + Message.objects.filter(
                conversation__user_high=request.user,
                is_read=False,
            )
            .exclude(sender=request.user)
            .count()
        )
        favorite_ids = set(
            Favorite.objects.filter(user=request.user).values_list("listing_id", flat=True)
        )
    staff_return_url = ""
    if request.user.is_authenticated and getattr(request.user, "is_staff", False):
        if not (request.path or "").startswith("/tableau-de-bord/"):
            staff_return_url = request.session.get("staff_return_url") or ""

    show_boost_fab = False
    boost_fab_url = ""
    boost_fab_label = "Booster"
    if request.user.is_authenticated:
        path = request.path or ""
        hide = path.startswith(
            ("/tableau-de-bord/", "/connexion", "/paiements/", "/messages", "/notifications")
        )
        if not hide:
            show_boost_fab = True
            boost_fab_url = "/profil/etre-recommande/"
            boost_fab_label = "Booster mon profil"
            match = getattr(request, "resolver_match", None)
            if match and match.namespace == "recommendations" and match.url_name in {
                "boost_profile",
                "boost_listing",
            }:
                show_boost_fab = False
            elif match and match.namespace == "listings" and match.url_name == "detail":
                listing_pk = match.kwargs.get("pk")
                if listing_pk:
                    from apps.listings.models import Listing

                    if Listing.objects.filter(pk=listing_pk, author_id=request.user.id).exists():
                        boost_fab_url = f"/annonces/{listing_pk}/recommander/"
                        boost_fab_label = "Booster l'annonce"

    android_app_url = str(getattr(settings, "ANDROID_APP_URL", "") or "").strip()
    ios_app_url = str(getattr(settings, "IOS_APP_URL", "") or "").strip()
    android_app_ready = android_app_url.startswith(("http://", "https://"))
    ios_app_ready = ios_app_url.startswith(("http://", "https://"))

    return {
        "site_name": settings.PUBLIC_SITE_NAME,
        "site_tagline": settings.PUBLIC_TAGLINE,
        "unread_notifications": unread,
        "unread_messages": unread_messages,
        "favorite_ids": favorite_ids,
        "safety_notice": "Fallaman ne demande jamais d'argent pour obtenir un emploi.",
        "staff_return_url": staff_return_url,
        "android_app_url": android_app_url or "#",
        "ios_app_url": ios_app_url or "#",
        "android_app_external": android_app_ready,
        "ios_app_external": ios_app_ready,
        "android_app_ready": android_app_ready,
        "ios_app_ready": ios_app_ready,
        "show_boost_fab": show_boost_fab,
        "boost_fab_url": boost_fab_url,
        "boost_fab_label": boost_fab_label,
        "show_staff_login": bool(getattr(settings, "DEV_CONVENIENCES", False)),
    }
