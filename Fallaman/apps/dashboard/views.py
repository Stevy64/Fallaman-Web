from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.dashboard.models import StaffBroadcast
from apps.interactions.models import Interest
from apps.listings.models import Favorite, Listing, SearchAlert
from apps.messaging.models import Conversation, Message
from apps.moderation.models import BlockedUser, Report
from apps.notifications.models import Notification
from apps.notifications.services import broadcast_notification
from apps.payments.models import PaymentTransaction
from apps.recommendations.models import CandidateIntroduction, RecommendationPurchase

User = get_user_model()
PAGE_SIZE = 24


def _page(queryset, request, size=PAGE_SIZE):
    paginator = Paginator(queryset, size)
    return paginator.get_page(request.GET.get("page") or 1)


def _safe_next(request, fallback):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return fallback


@staff_member_required
@require_GET
def dashboard(request):
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    now = timezone.now()
    pending = (
        Listing.objects.filter(status=Listing.Status.PENDING)
        .select_related("author", "author__profile", "city")
        .order_by("-created_at")[:8]
    )
    reports = (
        Report.objects.filter(status__in=[Report.Status.OPEN, Report.Status.IN_REVIEW])
        .select_related("listing", "reporter", "reporter__profile", "reported_user")
        .order_by("-created_at")[:8]
    )
    recent_users = User.objects.select_related("profile", "profile__city").order_by("-date_joined")[:6]
    recent_listings = (
        Listing.objects.exclude(status=Listing.Status.DELETED)
        .select_related("author", "author__profile", "city")
        .order_by("-created_at")[:6]
    )
    active_recos = (
        RecommendationPurchase.objects.filter(
            status=RecommendationPurchase.Status.ACTIVE,
            ends_at__gt=now,
        )
        .select_related("user", "user__profile", "listing", "profile")
        .order_by("-starts_at")[:8]
    )
    revenue_total = (
        PaymentTransaction.objects.filter(status=PaymentTransaction.Status.SUCCESS).aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )
    revenue_today = (
        PaymentTransaction.objects.filter(
            status=PaymentTransaction.Status.SUCCESS,
            paid_at__gte=today,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    staff_alerts = (
        Notification.objects.filter(
            user=request.user,
            kind__in=[
                Notification.Kind.STAFF_NEW_PROFILE,
                Notification.Kind.STAFF_NEW_LISTING,
                Notification.Kind.STAFF_RECOMMENDATION,
            ],
        )
        .order_by("-created_at")[:10]
    )
    context = {
        "section": "home",
        "users_count": User.objects.count(),
        "active_listings": Listing.objects.published().count(),
        "new_listings": Listing.objects.filter(created_at__gte=today).count(),
        "open_reports": Report.objects.filter(status=Report.Status.OPEN).count(),
        "messages_today": Message.objects.filter(created_at__gte=today).count(),
        "new_users": User.objects.filter(date_joined__gte=today).count(),
        "pending_count": Listing.objects.filter(status=Listing.Status.PENDING).count(),
        "suspended_count": User.objects.filter(is_active=False).count(),
        "active_reco_count": RecommendationPurchase.objects.filter(
            status=RecommendationPurchase.Status.ACTIVE, ends_at__gt=now
        ).count(),
        "revenue_total": revenue_total,
        "revenue_today": revenue_today,
        "pending_listings": pending,
        "reports": reports,
        "recent_users": recent_users,
        "recent_listings": recent_listings,
        "active_recos": active_recos,
        "staff_alerts": staff_alerts,
        "pending_intros": CandidateIntroduction.objects.filter(
            status=CandidateIntroduction.Status.PENDING
        ).count(),
    }
    return render(request, "dashboard/index.html", context)


@staff_member_required
@require_GET
def profiles(request):
    qs = User.objects.select_related(
        "profile", "profile__city", "profile__primary_profession"
    ).annotate(
        listing_count=Count("listings", filter=~Q(listings__status=Listing.Status.DELETED), distinct=True),
        report_count=Count("reports_received", distinct=True),
        interest_count=Count("interests", distinct=True),
    )
    q = (request.GET.get("q") or "").strip()
    status = request.GET.get("status") or "all"
    if q:
        qs = qs.filter(
            Q(phone_number__icontains=q)
            | Q(profile__display_name__icontains=q)
            | Q(profile__first_name__icontains=q)
            | Q(profile__last_name__icontains=q)
            | Q(profile__looking_for__icontains=q)
            | Q(profile__primary_profession__name__icontains=q)
        )
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "suspended":
        qs = qs.filter(is_active=False)
    elif status == "staff":
        qs = qs.filter(is_staff=True)
    elif status == "incomplete":
        qs = qs.filter(Q(profile__display_name="") | Q(profile__city__isnull=True))
    elif status == "reported":
        qs = qs.filter(report_count__gt=0)
    qs = qs.order_by("-date_joined")
    context = {
        "section": "profiles",
        "users": _page(qs, request),
        "q": q,
        "status": status,
    }
    template = (
        "dashboard/partials/profiles_results.html"
        if getattr(request, "htmx", False)
        else "dashboard/profiles.html"
    )
    return render(request, template, context)


@staff_member_required
@require_GET
def profile_detail(request, pk):
    member = get_object_or_404(
        User.objects.select_related(
            "profile",
            "profile__city",
            "profile__district",
            "profile__primary_profession",
        ),
        pk=pk,
    )
    listings = (
        Listing.objects.filter(author=member)
        .exclude(status=Listing.Status.DELETED)
        .select_related("city", "profession")
        .order_by("-created_at")[:20]
    )
    interests_out = (
        Interest.objects.filter(user=member)
        .select_related("listing", "listing__city")
        .order_by("-created_at")[:12]
    )
    interests_in = (
        Interest.objects.filter(listing__author=member)
        .select_related("user", "user__profile", "listing")
        .order_by("-created_at")[:12]
    )
    conversations = (
        Conversation.objects.filter(Q(user_low=member) | Q(user_high=member))
        .select_related("listing", "user_low", "user_high", "user_low__profile", "user_high__profile")
        .order_by("-last_message_at")[:12]
    )
    for convo in conversations:
        convo.counterpart = convo.other_user(member)
    reports_in = (
        Report.objects.filter(Q(reported_user=member) | Q(listing__author=member))
        .select_related("reporter", "listing")
        .distinct()
        .order_by("-created_at")[:12]
    )
    reports_out = Report.objects.filter(reporter=member).select_related("listing").order_by("-created_at")[:8]
    blocks_made = BlockedUser.objects.filter(blocker=member).select_related("blocked", "blocked__profile")
    blocks_got = BlockedUser.objects.filter(blocked=member).select_related("blocker", "blocker__profile")
    alerts = SearchAlert.objects.filter(user=member).order_by("-created_at")[:8]
    favorites = (
        Favorite.objects.filter(user=member).select_related("listing", "listing__city").order_by("-created_at")[:8]
    )

    activity = []
    for listing in listings:
        activity.append(
            {
                "when": listing.created_at,
                "icon": "briefcase",
                "label": "Annonce publiée" if listing.status == Listing.Status.PUBLISHED else "Annonce",
                "text": listing.title,
                "meta": listing.get_status_display(),
            }
        )
    for item in interests_out:
        activity.append(
            {
                "when": item.created_at,
                "icon": "hand-thumbs-up",
                "label": "Intérêt envoyé",
                "text": item.listing.title,
                "meta": "",
            }
        )
    for item in interests_in:
        activity.append(
            {
                "when": item.created_at,
                "icon": "inbox",
                "label": "Intérêt reçu",
                "text": f"{item.user.display_name} · {item.listing.title}",
                "meta": "",
            }
        )
    for convo in conversations:
        activity.append(
            {
                "when": convo.last_message_at,
                "icon": "chat",
                "label": "Discussion",
                "text": convo.listing.title,
                "meta": convo.other_user(member).display_name,
            }
        )
    for report in reports_in[:6]:
        activity.append(
            {
                "when": report.created_at,
                "icon": "flag",
                "label": "Signalement reçu",
                "text": report.get_reason_display(),
                "meta": report.get_status_display(),
            }
        )
    activity.sort(key=lambda event: event["when"] or timezone.now(), reverse=True)

    stats = {
        "listings": Listing.objects.filter(author=member).exclude(status=Listing.Status.DELETED).count(),
        "published": Listing.objects.filter(author=member, status=Listing.Status.PUBLISHED).count(),
        "interests_out": Interest.objects.filter(user=member).count(),
        "interests_in": Interest.objects.filter(listing__author=member).count(),
        "messages": Message.objects.filter(sender=member).count(),
        "reports": Report.objects.filter(Q(reported_user=member) | Q(listing__author=member)).distinct().count(),
    }
    return render(
        request,
        "dashboard/profile_detail.html",
        {
            "section": "profiles",
            "member": member,
            "profile": getattr(member, "profile", None),
            "listings": listings,
            "interests_out": interests_out,
            "interests_in": interests_in,
            "conversations": conversations,
            "reports_in": reports_in,
            "reports_out": reports_out,
            "blocks_made": blocks_made,
            "blocks_got": blocks_got,
            "alerts": alerts,
            "favorites": favorites,
            "activity": activity[:20],
            "stats": stats,
        },
    )


@staff_member_required
@require_GET
def listings(request):
    qs = Listing.objects.select_related("author", "author__profile", "city", "profession").exclude(
        status=Listing.Status.DELETED
    )
    status = request.GET.get("status") or "all"
    q = (request.GET.get("q") or "").strip()
    listing_type = request.GET.get("type") or ""
    if status != "all":
        qs = qs.filter(status=status)
    if listing_type in {Listing.Type.EMPLOYMENT, Listing.Type.MISSION}:
        qs = qs.filter(listing_type=listing_type)
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(author__phone_number__icontains=q)
            | Q(author__profile__display_name__icontains=q)
        )
    qs = qs.order_by("-created_at")
    context = {
        "section": "listings",
        "listings": _page(qs, request),
        "status": status,
        "q": q,
        "listing_type": listing_type,
    }
    template = (
        "dashboard/partials/listings_results.html"
        if getattr(request, "htmx", False)
        else "dashboard/listings.html"
    )
    return render(request, template, context)


@staff_member_required
@require_POST
def listing_action(request, pk, action):
    listing = get_object_or_404(Listing, pk=pk)
    if action == "publish":
        listing.publish()
        messages.success(request, "Annonce publiée.")
    elif action == "hide":
        listing.status = Listing.Status.HIDDEN
        listing.save(update_fields=["status", "updated_at"])
        messages.info(request, "Annonce masquée.")
    elif action == "reject":
        listing.status = Listing.Status.REJECTED
        listing.save(update_fields=["status", "updated_at"])
        messages.info(request, "Annonce rejetée.")
    elif action == "delete":
        listing.status = Listing.Status.DELETED
        listing.save(update_fields=["status", "updated_at"])
        messages.info(request, "Annonce retirée.")
    else:
        messages.error(request, "Action inconnue.")
    return redirect(_safe_next(request, reverse("dashboard:listings")))


@staff_member_required
@require_POST
def user_action(request, pk, action):
    member = get_object_or_404(User, pk=pk)
    fallback = reverse("dashboard:profile_detail", args=[member.pk])
    if member == request.user and action in {"suspend", "activate"}:
        messages.error(request, "Vous ne pouvez pas modifier votre propre accès ici.")
        return redirect(_safe_next(request, fallback))
    if action == "suspend":
        member.is_active = False
        member.save(update_fields=["is_active"])
        messages.info(request, f"{member.display_name} a été suspendu(e).")
    elif action == "activate":
        member.is_active = True
        member.save(update_fields=["is_active"])
        messages.success(request, f"{member.display_name} a été réactivé(e).")
    elif action == "verify":
        member.phone_verified = True
        member.save(update_fields=["phone_verified"])
        messages.success(request, "Téléphone marqué comme vérifié.")
    else:
        messages.error(request, "Action inconnue.")
    return redirect(_safe_next(request, fallback))


@staff_member_required
@require_GET
def reports(request):
    qs = Report.objects.select_related(
        "listing",
        "listing__author",
        "reporter",
        "reporter__profile",
        "reported_user",
        "reported_user__profile",
    )
    status = request.GET.get("status") or "open"
    if status == "open":
        qs = qs.filter(status__in=[Report.Status.OPEN, Report.Status.IN_REVIEW])
    elif status != "all":
        qs = qs.filter(status=status)
    return render(
        request,
        "dashboard/reports.html",
        {
            "section": "reports",
            "reports": _page(qs.order_by("-created_at"), request),
            "status": status,
        },
    )


@staff_member_required
@require_POST
def report_action(request, pk, action):
    report = get_object_or_404(Report, pk=pk)
    if action == "review":
        report.status = Report.Status.IN_REVIEW
        messages.info(request, "Signalement pris en charge.")
    elif action == "resolve":
        report.status = Report.Status.RESOLVED
        messages.success(request, "Signalement traité.")
    elif action == "reject":
        report.status = Report.Status.REJECTED
        messages.info(request, "Signalement rejeté.")
    else:
        messages.error(request, "Action inconnue.")
        return redirect("dashboard:reports")
    report.save(update_fields=["status"])
    return redirect(_safe_next(request, reverse("dashboard:reports")))


@staff_member_required
@require_GET
def recommendations(request):
    now = timezone.now()
    qs = RecommendationPurchase.objects.select_related(
        "user", "user__profile", "listing", "profile", "payment"
    )
    status = request.GET.get("status") or "active"
    if status == "active":
        qs = qs.filter(status=RecommendationPurchase.Status.ACTIVE, ends_at__gt=now)
    elif status != "all":
        qs = qs.filter(status=status)
    revenue = (
        PaymentTransaction.objects.filter(status=PaymentTransaction.Status.SUCCESS).aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )
    revenue_by_purpose = (
        PaymentTransaction.objects.filter(status=PaymentTransaction.Status.SUCCESS)
        .values("purpose")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    intros = (
        CandidateIntroduction.objects.select_related(
            "listing", "profile", "profile__user", "employer", "employer__profile"
        )
        .order_by("-created_at")[:20]
    )
    return render(
        request,
        "dashboard/recommendations.html",
        {
            "section": "recommendations",
            "purchases": _page(qs.order_by("-created_at"), request),
            "status": status,
            "revenue": revenue,
            "revenue_by_purpose": revenue_by_purpose,
            "intros": intros,
            "active_count": RecommendationPurchase.objects.filter(
                status=RecommendationPurchase.Status.ACTIVE, ends_at__gt=now
            ).count(),
        },
    )


def _send_staff_broadcast(request, *, title: str, body: str, audience: str, recipient_id: str | None):
    """Crée la diffusion + notifications. Retourne (ok, message flash)."""
    recipient = None
    if audience == StaffBroadcast.Audience.ONE:
        if not recipient_id:
            return False, "Choisissez le destinataire."
        recipient = (
            User.objects.filter(pk=recipient_id, is_active=True)
            .select_related("profile")
            .first()
        )
        if recipient is None:
            return False, "Destinataire introuvable ou inactif."
        count = broadcast_notification(
            title=title, body=body, audience=audience, recipient=recipient
        )
    elif audience in {StaffBroadcast.Audience.ALL, StaffBroadcast.Audience.ACTIVE}:
        count = broadcast_notification(title=title, body=body, audience=audience)
    else:
        return False, "Audience invalide."

    StaffBroadcast.objects.create(
        author=request.user,
        title=title[:160],
        body=body[:2000],
        audience=audience,
        recipient=recipient,
        recipient_count=count,
    )
    if audience == StaffBroadcast.Audience.ONE and recipient:
        return True, f"Message envoyé à {recipient.display_name}."
    return True, f"Message envoyé à {count} membre(s)."


@staff_member_required
@require_http_methods(["GET", "POST"])
def team_messaging(request):
    """Hub messagerie équipe : conversations + diffusions."""
    tab = (request.GET.get("tab") or "conversations").strip()
    if tab not in {"conversations", "diffusions"}:
        tab = "conversations"

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        body = (request.POST.get("body") or "").strip()
        audience = request.POST.get("audience") or StaffBroadcast.Audience.ACTIVE
        recipient_id = (request.POST.get("recipient_id") or "").strip() or None
        if not title or not body:
            messages.error(request, "Titre et message obligatoires.")
            return redirect(f"{reverse('dashboard:staff_messaging')}?tab=diffusions")
        ok, flash = _send_staff_broadcast(
            request,
            title=title,
            body=body,
            audience=audience,
            recipient_id=recipient_id,
        )
        if ok:
            messages.success(request, flash)
        else:
            messages.error(request, flash)
        return redirect(f"{reverse('dashboard:staff_messaging')}?tab=diffusions")

    context = {
        "section": "messaging",
        "tab": tab,
        "history": StaffBroadcast.objects.select_related(
            "author", "author__profile", "recipient", "recipient__profile"
        ).order_by("-created_at")[:30],
        "q": "",
        "show": "all",
        "conversations": [],
        "members": [],
    }

    if tab == "conversations":
        qs = Conversation.objects.select_related(
            "listing",
            "user_low",
            "user_high",
            "user_low__profile",
            "user_high__profile",
        ).annotate(message_count=Count("messages"))
        q = (request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(listing__title__icontains=q)
                | Q(user_low__phone_number__icontains=q)
                | Q(user_high__phone_number__icontains=q)
                | Q(user_low__profile__display_name__icontains=q)
                | Q(user_high__profile__display_name__icontains=q)
            )
        show = request.GET.get("show") or "all"
        if show == "live":
            qs = qs.filter(is_expired=False)
        elif show == "expired":
            qs = qs.filter(is_expired=True)
        context.update(
            {
                "conversations": _page(qs.order_by("-last_message_at"), request),
                "q": q,
                "show": show,
            }
        )
        if getattr(request, "htmx", False):
            return render(request, "dashboard/partials/messaging_conversations.html", context)
    else:
        context["members"] = (
            User.objects.filter(is_active=True, is_staff=False)
            .select_related("profile")
            .order_by("profile__display_name", "phone_number")[:800]
        )

    return render(request, "dashboard/messaging.html", context)


@staff_member_required
@require_GET
def conversations(request):
    query = request.GET.urlencode()
    target = reverse("dashboard:staff_messaging")
    return redirect(f"{target}?tab=conversations" + (f"&{query}" if query else ""))


@staff_member_required
@require_GET
def conversation_detail(request, pk):
    conversation = get_object_or_404(
        Conversation.objects.select_related(
            "listing",
            "user_low",
            "user_high",
            "user_low__profile",
            "user_high__profile",
        ),
        pk=pk,
    )
    chat_messages = conversation.messages.select_related("sender", "sender__profile")
    return render(
        request,
        "dashboard/conversation_detail.html",
        {
            "section": "messaging",
            "conversation": conversation,
            "chat_messages": chat_messages,
            "read_only": True,
        },
    )


@staff_member_required
@require_http_methods(["GET", "POST"])
def broadcast(request):
    if request.method == "POST":
        # Compat : poster encore vers l'ancienne URL
        title = (request.POST.get("title") or "").strip()
        body = (request.POST.get("body") or "").strip()
        audience = request.POST.get("audience") or StaffBroadcast.Audience.ACTIVE
        recipient_id = (request.POST.get("recipient_id") or "").strip() or None
        if title and body:
            ok, flash = _send_staff_broadcast(
                request,
                title=title,
                body=body,
                audience=audience,
                recipient_id=recipient_id,
            )
            if ok:
                messages.success(request, flash)
            else:
                messages.error(request, flash)
        else:
            messages.error(request, "Titre et message obligatoires.")
        return redirect(f"{reverse('dashboard:staff_messaging')}?tab=diffusions")
    return redirect(f"{reverse('dashboard:staff_messaging')}?tab=diffusions")


@staff_member_required
@require_GET
def alerts(request):
    qs = Notification.objects.filter(
        user=request.user,
        kind__in=[
            Notification.Kind.STAFF_NEW_PROFILE,
            Notification.Kind.STAFF_NEW_LISTING,
            Notification.Kind.STAFF_RECOMMENDATION,
        ],
    ).order_by("-created_at")
    return render(
        request,
        "dashboard/alerts.html",
        {
            "section": "alerts",
            "alerts": _page(qs, request, size=40),
        },
    )


@staff_member_required
@require_GET
def activity_logs(request):
    from apps.core.models import ActivityLog

    qs = ActivityLog.objects.select_related("user", "user__profile")
    q = (request.GET.get("q") or "").strip()
    level = (request.GET.get("level") or "").strip()
    category = (request.GET.get("category") or "").strip()
    if q:
        qs = qs.filter(
            Q(action__icontains=q)
            | Q(message__icontains=q)
            | Q(path__icontains=q)
            | Q(user__phone_number__icontains=q)
        )
    if level:
        qs = qs.filter(level=level)
    if category:
        qs = qs.filter(category=category)
    context = {
        "section": "logs",
        "logs": _page(qs, request, size=40),
        "q": q,
        "level": level,
        "category": category,
        "levels": ActivityLog.Level.choices,
        "categories": ActivityLog.Category.choices,
    }
    template = (
        "dashboard/partials/activity_logs_results.html"
        if getattr(request, "htmx", False)
        else "dashboard/activity_logs.html"
    )
    return render(request, template, context)
