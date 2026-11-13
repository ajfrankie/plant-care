"""Watering reminders: when each plant needs water, and marking it done."""
from datetime import timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import care_plan
from ..forms import WaterReminderForm
from ..models import CareTask, Plant, WaterReminder

SHOW = {
    "": "All Reminders",
    "due": "Due Today / Overdue",
    "week": "Coming Up This Week",
    "later": "Later",
    "recent": "Recently Watered",
    "paused": "Paused",
}
SORTS = {
    "due": ("Due Date", ["next_due_date", "plant__name"]),
    "name": ("Plant Name", ["plant__name", "next_due_date"]),
    "last": ("Last Watered", ["-last_watered_at", "plant__name"]),
    "frequency": ("Frequency", ["frequency_days", "plant__name"]),
}
RECENT_DAYS = 7


def _user_reminders(request):
    return WaterReminder.objects.filter(plant__created_user=request.user).select_related(
        "plant", "plant__plant_species"
    )


def _suggested_days(plant):
    """Watering interval the care-plan analysis recommends for ``plant``."""
    water = next(p for p in care_plan.analyse(plant) if p.kind == CareTask.Kind.WATER)
    return water.every_days


def _plants_without_reminder(user):
    return Plant.objects.filter(created_user=user, water_reminders__isnull=True)


def index(request):
    today = timezone.localdate()
    week_end = today + timedelta(days=6)
    recent_since = timezone.now() - timedelta(days=RECENT_DAYS)

    show = request.GET.get("show", "")
    if show not in SHOW:
        show = ""
    sort = request.GET.get("sort", "due")
    if sort not in SORTS:
        sort = "due"

    reminders = _user_reminders(request)
    active = reminders.filter(is_active=True)
    order = SORTS[sort][1]

    sections = {
        "due": active.filter(next_due_date__lte=today),
        "week": active.filter(next_due_date__gt=today, next_due_date__lte=week_end),
        "later": active.filter(next_due_date__gt=week_end),
        "recent": reminders.filter(last_watered_at__gte=recent_since),
        "paused": reminders.filter(is_active=False),
    }
    stats = {
        "due": sections["due"].count(),
        "week": active.filter(next_due_date__lte=week_end).count(),
        "recent": sections["recent"].count(),
        "active": active.count(),
    }
    shown = {
        key: list(qs.order_by(*(["-last_watered_at"] if key == "recent" else order)))
        for key, qs in sections.items()
        if show in ("", key)
    }

    return render(request, "care/watering.html", {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "stats": stats,
        "sections": shown,
        "show": show,
        "show_choices": SHOW.items(),
        "sort": sort,
        "sort_choices": [(key, label) for key, (label, _) in SORTS.items()],
        "has_reminders": reminders.exists(),
        "has_plants": Plant.objects.filter(created_user=request.user).exists(),
        "without_reminder": _plants_without_reminder(request.user).count(),
        "next_url": request.get_full_path(),
    })


def _form_page(request, form, reminder=None):
    plants = Plant.objects.filter(created_user=request.user).select_related("plant_species")
    return render(request, "care/watering_form.html", {
        "form": form,
        "reminder": reminder,
        "suggestions": {str(p.pk): _suggested_days(p) for p in plants},
        "method_choices": WaterReminder.Method.choices,
        "today": timezone.localdate(),
    })


def add(request):
    initial = {"next_due_date": timezone.localdate().isoformat(), "reminder_time": "09:00"}
    plant_id = request.GET.get("plant", "")
    if plant_id.isdigit():
        plant = Plant.objects.filter(pk=plant_id, created_user=request.user).first()
        if plant:
            initial.update(plant=plant.pk, frequency_days=_suggested_days(plant))
    form = WaterReminderForm(request.POST or None, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        reminder = form.save()
        messages.success(request, f"Watering reminder for {reminder.plant.name} was added.")
        return redirect("watering_schedule")
    return _form_page(request, form)


def edit(request, pk):
    reminder = get_object_or_404(_user_reminders(request), pk=pk)
    form = WaterReminderForm(
        request.POST or None, user=request.user,
        instance=WaterReminder.objects.get(pk=reminder.pk),
    )
    if request.method == "POST" and form.is_valid():
        updated = form.save()
        messages.success(request, f"Watering reminder for {updated.plant.name} was updated.")
        return redirect("watering_schedule")
    return _form_page(request, form, reminder)


def _back(request):
    target = request.POST.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return redirect(target)
    return redirect("watering_schedule")


@require_POST
def water(request, pk):
    reminder = get_object_or_404(_user_reminders(request), pk=pk)
    reminder.mark_watered()
    messages.success(
        request,
        f"{reminder.plant.name} watered. Next watering: {reminder.next_due_date:%b} {reminder.next_due_date.day}.",
    )
    return _back(request)


@require_POST
def water_all(request):
    due = _user_reminders(request).filter(is_active=True, next_due_date__lte=timezone.localdate())
    names = []
    for reminder in due:
        reminder.mark_watered()
        names.append(reminder.plant.name)
    if names:
        messages.success(request, f"Marked {len(names)} plant{'s' if len(names) != 1 else ''} as watered: {', '.join(names)}.")
    else:
        messages.success(request, "Nothing needs water right now.")
    return _back(request)


@require_POST
def toggle(request, pk):
    reminder = get_object_or_404(_user_reminders(request), pk=pk)
    reminder.is_active = not reminder.is_active
    if reminder.is_active and reminder.next_due_date < timezone.localdate():
        # Resuming after a pause: start counting again from today.
        reminder.next_due_date = timezone.localdate()
    reminder.save(update_fields=["is_active", "next_due_date", "updated_at"])
    state = "resumed" if reminder.is_active else "paused"
    messages.success(request, f"Watering reminder for {reminder.plant.name} {state}.")
    return _back(request)


@require_POST
def delete(request, pk):
    reminder = get_object_or_404(_user_reminders(request), pk=pk)
    reminder.delete()
    messages.success(request, f"Watering reminder for {reminder.plant.name} was removed.")
    return _back(request)


@require_POST
def auto_create(request):
    """Add a reminder, at the analysed interval, for every plant without one."""
    today = timezone.localdate()
    plants = list(_plants_without_reminder(request.user).select_related("plant_species"))
    WaterReminder.objects.bulk_create([
        WaterReminder(plant=plant, frequency_days=_suggested_days(plant), next_due_date=today)
        for plant in plants
    ])
    if plants:
        messages.success(request, f"Watering reminders added for {', '.join(p.name for p in plants)}.")
    else:
        messages.success(request, "Every plant already has a watering reminder.")
    return _back(request)
