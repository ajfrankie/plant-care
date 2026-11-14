"""Notifications page and actions."""
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .. import notify
from ..models import Notification

PER_PAGE = 20
Kind = Notification.Kind

# key: (label, filter)
FILTERS = {
    "all": ("All", Q()),
    "unread": ("Unread", Q(is_read=False)),
    "reminders": ("Care Reminders", Q(kind__in=[Kind.REMINDER, Kind.OVERDUE])),
    "health": ("Health Alerts", Q(kind=Kind.HEALTH)),
    "completed": ("Completed", Q(kind=Kind.COMPLETED)),
}

# Colours and icon per kind (icon names match care/_kind_icon.html where possible).
STYLES = {
    Kind.REMINDER: {"color": "var(--info)", "bg": "var(--info-bg)", "icon": "water"},
    Kind.OVERDUE: {"color": "var(--warning)", "bg": "var(--warning-bg)", "icon": "overdue"},
    Kind.HEALTH: {"color": "var(--error)", "bg": "var(--error-bg)", "icon": "health"},
    Kind.COMPLETED: {"color": "var(--success)", "bg": "var(--success-bg)", "icon": "done"},
}


def _visible(user):
    return Notification.objects.filter(recipient=user, is_dismissed=False)


def _decorate(notifications):
    for n in notifications:
        style = STYLES.get(n.kind, STYLES[Kind.REMINDER])
        n.color, n.bg, n.icon = style["color"], style["bg"], style["icon"]
        if n.task_id and n.kind != Kind.OVERDUE:
            n.icon = n.task.kind  # water / fertilize / prune / health
    return notifications


def _section(created, today):
    day = timezone.localdate(created)
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    if day > today - timedelta(days=7):
        return "Earlier This Week"
    return "Older"


def _back(request):
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                       require_https=request.is_secure()):
        return redirect(target)
    return redirect("notifications")


def _own(request, pk):
    return get_object_or_404(
        Notification.objects.select_related("task", "water_reminder", "plant"),
        pk=pk, recipient=request.user, is_dismissed=False,
    )


def index(request):
    notify.sync(request.user)
    request.notifications_synced = True  # the header bell needn't sync again
    today = timezone.localdate()
    show = request.GET.get("show", "all")
    if show not in FILTERS:
        show = "all"

    visible = _visible(request.user)
    counts = visible.aggregate(**{key: Count("pk", filter=q) for key, (_, q) in FILTERS.items()})
    listed = (
        visible.filter(FILTERS[show][1])
        .select_related("plant", "task", "water_reminder")
        .order_by("-created_at", "-pk")
    )
    page = Paginator(listed, PER_PAGE).get_page(request.GET.get("page"))
    _decorate(page.object_list)
    sections = []
    for n in page.object_list:
        name = _section(n.created_at, today)
        if not sections or sections[-1][0] != name:
            sections.append((name, []))
        sections[-1][1].append(n)

    return render(request, "accounts/notifications.html", {
        "show": show,
        "show_label": FILTERS[show][0],
        "filters": [(key, label, counts[key]) for key, (label, _) in FILTERS.items()],
        "unread_count": counts["unread"],
        "total_count": counts["all"],
        "page": page,
        "sections": sections,
        "next_url": request.get_full_path(),
    })


def open_notification(request, pk):
    """Mark as read and go to what it is about."""
    notification = _own(request, pk)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return redirect(notification.target_url)


@require_POST
def toggle_read(request, pk):
    notification = _own(request, pk)
    notification.is_read = not notification.is_read
    notification.save(update_fields=["is_read"])
    return _back(request)


@require_POST
def complete(request, pk):
    """Do the care the notification is about (water, fertilize, ...)."""
    notification = _own(request, pk)
    if not notification.can_complete:
        messages.info(request, "That has already been done.")
    elif notification.task_id:
        task = notification.task
        next_task = task.complete()
        message = f"{task.get_kind_display()} for {task.plant.name} marked as done."
        if next_task:
            message += f" Next one is due {next_task.due_date:%b} {next_task.due_date.day}."
        messages.success(request, message)
    else:
        reminder = notification.water_reminder
        reminder.mark_watered()
        messages.success(request, f"{reminder.plant.name} marked as watered.")
    Notification.objects.filter(pk=notification.pk).update(is_read=True)
    return _back(request)


@require_POST
def dismiss(request, pk):
    notification = _own(request, pk)
    notification.is_dismissed = True
    notification.is_read = True
    notification.save(update_fields=["is_dismissed", "is_read"])
    return _back(request)


@require_POST
def read_all(request):
    updated = _visible(request.user).filter(is_read=False).update(is_read=True)
    if updated:
        messages.success(request, f"{updated} notification{'s' if updated != 1 else ''} marked as read.")
    return _back(request)


@require_POST
def clear_all(request):
    cleared = _visible(request.user).update(is_dismissed=True, is_read=True)
    if cleared:
        messages.success(request, f"{cleared} notification{'s' if cleared != 1 else ''} cleared.")
    return _back(request)
