from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.redirects import is_safe_target

from .models import Notification


def _wants_json(request) -> bool:
    accept = request.headers.get("Accept", "")
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in accept
        or request.GET.get("format") == "json"
    )


@login_required
def notification_list(request):
    items = Notification.objects.filter(user=request.user)
    return render(request, "notifications/list.html", {"notifications": items})


@login_required
def open_notification(request, pk):
    """Ouvre une notification.

    Classique : consultation = suppression.
    Message équipe : marquée lue, conservée jusqu'à suppression explicite.
    """
    notification = get_object_or_404(Notification, pk=pk, user=request.user)

    if notification.is_persistent:
        notification.mark_read()
        payload = {
            "id": notification.pk,
            "title": notification.title,
            "body": notification.body or "",
            "created_at": timezone.localtime(notification.created_at).strftime("%d/%m/%Y %H:%M"),
            "kind": notification.kind,
            "persistent": True,
        }
        if _wants_json(request):
            return JsonResponse(payload)
        return render(
            request,
            "notifications/broadcast_detail.html",
            {"notification": notification, "section": "notifications"},
        )

    target = notification.url or ""
    notification.delete()
    if is_safe_target(target, request=request):
        return redirect(target)
    return redirect("notifications:list")


@login_required
@require_POST
def delete_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.delete()
    if request.headers.get("HX-Request") or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return HttpResponse("")
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )
    return redirect("notifications:list")
