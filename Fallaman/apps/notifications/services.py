from django.contrib.auth import get_user_model

from .models import Notification

User = get_user_model()


def notify(user, kind: str, title: str, url: str = "") -> Notification:
    return Notification.objects.create(user=user, kind=kind, title=title, url=url)


def notify_recommendation(user, listing) -> Notification | None:
    """Notifie un utilisateur qu'un poste correspond à sa recherche."""
    url = listing.get_absolute_url()
    already = Notification.objects.filter(
        user=user,
        kind=Notification.Kind.NEW_MATCHING_LISTING,
        url=url,
    ).exists()
    if already:
        return None
    job = listing.job_label
    return notify(
        user,
        Notification.Kind.NEW_MATCHING_LISTING,
        f"Nouveau poste pour votre recherche : {job}",
        url=url,
    )


def notify_staff(kind: str, title: str, url: str = "") -> int:
    """Crée une notification pour tous les comptes staff actifs."""
    staff_ids = list(
        User.objects.filter(is_staff=True, is_active=True).values_list("id", flat=True)
    )
    if not staff_ids:
        return 0
    Notification.objects.bulk_create(
        [
            Notification(user_id=uid, kind=kind, title=title, url=url)
            for uid in staff_ids
        ]
    )
    return len(staff_ids)


def broadcast_notification(
    *,
    title: str,
    body: str,
    url: str = "",
    audience: str = "active",
    recipient=None,
) -> int:
    """Envoie une notification équipe (broadcast admin ou destinataire unique)."""
    if audience == "one":
        if recipient is None or not getattr(recipient, "is_active", False):
            return 0
        users = [recipient.pk]
    else:
        qs = User.objects.filter(is_active=True)
        if audience == "active":
            qs = qs.filter(is_staff=False)
        users = list(qs.values_list("id", flat=True))
    if not users:
        return 0
    Notification.objects.bulk_create(
        [
            Notification(
                user_id=uid,
                kind=Notification.Kind.STAFF_BROADCAST,
                title=title[:200],
                body=(body or "")[:2000],
                url=url,
            )
            for uid in users
        ],
        batch_size=500,
    )
    return len(users)
