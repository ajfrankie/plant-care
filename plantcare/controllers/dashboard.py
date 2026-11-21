"""The two dashboards: each user's own, and the admin overview of the whole site."""
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import CareLog, CareTask, HealthCase, Plant, PlantSpecies, User, WaterReminder

WATER_AHEAD_DAYS = 7  # how far ahead "Upcoming Watering" looks
RECENT_DAYS = 7       # admin activity window


def _greeting(user):
    hour = timezone.localtime().hour
    if hour < 12:
        part = "morning"
    elif hour < 18:
        part = "afternoon"
    else:
        part = "evening"
    name = f", {user.first_name}" if user.first_name else ""
    return f"Good {part}{name}"


# ---------- User dashboard ----------

def index(request):
    user = request.user
    today = timezone.localdate()

    plants = Plant.objects.filter(created_user=user)
    open_tasks = CareTask.objects.filter(plant__created_user=user, completed_at__isnull=True)
    reminders = WaterReminder.objects.filter(plant__created_user=user, is_active=True)

    due_tasks = list(
        open_tasks.filter(due_date__lte=today).select_related("plant").order_by("due_date", "plant__name")
    )
    # Plants needing water: a water reminder or a watering task due today or earlier.
    thirsty = set(reminders.filter(next_due_date__lte=today).values_list("plant_id", flat=True))
    thirsty |= {t.plant_id for t in due_tasks if t.kind == CareTask.Kind.WATER}

    counts = plants.aggregate(
        total=Count("pk"),
        healthy=Count("pk", filter=Q(status=Plant.Status.HEALTHY)),
        attention=Count("pk", filter=~Q(status=Plant.Status.HEALTHY)),
    )
    stats = {
        **counts,
        "thirsty": len(thirsty),
        "tasks_today": len(due_tasks),
        "overdue": sum(t.due_date < today for t in due_tasks),
    }

    recent_plants = list(
        plants.select_related("plant_species")
        .annotate(last_care_at=Max("care_logs__performed_at"))
        .order_by("-created_at")[:4]
    )
    upcoming_water = list(
        reminders.filter(next_due_date__lte=today + timedelta(days=WATER_AHEAD_DAYS))
        .select_related("plant").order_by("next_due_date", "plant__name")[:6]
    )
    for reminder in upcoming_water:
        reminder.days = (reminder.next_due_date - today).days
    for task in due_tasks:
        task.days_late = (today - task.due_date).days

    open_cases = list(
        HealthCase.objects.filter(plant__created_user=user)
        .exclude(status=HealthCase.Status.RESOLVED)
        .select_related("plant").order_by("next_check_date")[:4]
    )
    for case in open_cases:
        case.days = (case.next_check_date - today).days

    recent_logs = list(
        CareLog.objects.filter(plant__created_user=user).select_related("plant")[:5]
    )

    return render(request, "dashboard/dashboard.html", {
        "greeting": _greeting(user),
        "stats": stats,
        "recent_plants": recent_plants,
        "due_tasks": due_tasks[:8],
        "more_tasks": max(len(due_tasks) - 8, 0),
        "upcoming_water": upcoming_water,
        "open_cases": open_cases,
        "recent_logs": recent_logs,
    })


# ---------- Admin dashboard ----------

def _require_admin(request):
    if not request.user.is_staff:
        raise PermissionDenied("Only admins can open the admin dashboard.")


def admin_index(request):
    _require_admin(request)
    now = timezone.now()
    since = now - timedelta(days=RECENT_DAYS)

    users = User.objects.all()
    user_stats = users.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        pending=Count("pk", filter=Q(is_active=False)),
        admins=Count("pk", filter=Q(role=User.Role.ADMIN)),
        new=Count("pk", filter=Q(created_at__gte=since)),
    )
    plant_stats = Plant.objects.aggregate(
        total=Count("pk"),
        healthy=Count("pk", filter=Q(status=Plant.Status.HEALTHY)),
        attention=Count("pk", filter=Q(status=Plant.Status.ATTENTION)),
        critical=Count("pk", filter=Q(status=Plant.Status.CRITICAL)),
        new=Count("pk", filter=Q(created_at__gte=since)),
    )
    open_cases = HealthCase.objects.exclude(status=HealthCase.Status.RESOLVED)
    stats = {
        "users": user_stats,
        "plants": plant_stats,
        "species": PlantSpecies.objects.count(),
        "open_cases": open_cases.count(),
        "logs_week": CareLog.objects.filter(performed_at__gte=since).count(),
        "overdue_tasks": CareTask.objects.filter(
            completed_at__isnull=True, due_date__lt=timezone.localdate()
        ).count(),
    }

    pending = list(users.filter(is_active=False).order_by("created_at")[:10])
    recent_users = list(
        users.annotate(plant_count=Count("plants")).order_by("-created_at")[:8]
    )
    activity = [
        (label, CareLog.objects.filter(performed_at__gte=since, activity=value).count())
        for value, label in CareLog.Activity.choices
    ]
    top_species = list(
        PlantSpecies.objects.annotate(plant_count=Count("plants"))
        .filter(plant_count__gt=0).order_by("-plant_count", "common_name")[:5]
    )
    severity_order = {"severe": 0, "moderate": 1, "mild": 2}
    cases = sorted(
        open_cases.select_related("plant", "plant__created_user")[:20],
        key=lambda c: (severity_order.get(c.severity, 3), -c.started_at.timestamp()),
    )[:5]

    return render(request, "dashboard/admin.html", {
        "stats": stats,
        "pending": pending,
        "recent_users": recent_users,
        "activity": activity,
        "top_species": top_species,
        "cases": cases,
    })


@require_POST
def admin_toggle_user(request, pk):
    """Activate a pending account, or deactivate an active one."""
    _require_admin(request)
    member = get_object_or_404(User, pk=pk)
    if member.pk == request.user.pk:
        messages.error(request, "You can't deactivate your own account.")
    else:
        member.is_active = not member.is_active
        member.save(update_fields=["is_active", "updated_at"])
        state = "activated" if member.is_active else "deactivated"
        messages.success(request, f"{member.full_name or member.email} was {state}.")
    return redirect("admin_dashboard")
