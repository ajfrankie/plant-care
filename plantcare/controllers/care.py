"""Care schedules and history."""
import calendar
import copy
from datetime import date, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .. import care_plan
from ..forms import CareTaskForm
from ..models import CareTask, Plant

VIEWS = {"week": "Week View", "month": "Month View", "list": "List View"}
LIST_STATUSES = {"open": "Open Tasks", "done": "Completed", "all": "All Tasks"}
TASKS_PER_PAGE = 10


def _week_start(day):
    """The Sunday on or before ``day`` (weeks run Sunday to Saturday)."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def _without_schedule(plants):
    """Plants that have no open (not yet done) care tasks."""
    has_open = CareTask.objects.filter(completed_at__isnull=True).values("plant_id")
    return plants.exclude(pk__in=has_open)


def _repeats(task, today, start, end):
    """Days in [start, end] a repeating open task will come round again.

    The next one is scheduled from when the task is completed, so counting
    starts from its due date, or from today if it is already overdue.
    """
    every = task.repeat_every_days
    day = max(task.due_date, today) + timedelta(days=every)
    if day < start:
        day += timedelta(days=-(-(start - day).days // every) * every)
    while day <= end:
        yield day
        day += timedelta(days=every)


def _planned(task, day):
    """A copy of ``task`` shown on a later day, not saved."""
    occurrence = copy.copy(task)
    occurrence.due_date = day
    occurrence.planned = True
    return occurrence


def _parse_date(value, default):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


def _calendar_range(view, anchor):
    """(first day, last day, prev anchor, next anchor, label) for the calendar."""
    if view == "month":
        first = anchor.replace(day=1)
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        prev_month = (first - timedelta(days=1)).replace(day=1)
        next_month = last + timedelta(days=1)
        start = _week_start(first)
        end = _week_start(last) + timedelta(days=6)
        return start, end, prev_month, next_month, first.strftime("%B %Y")

    start = _week_start(anchor)
    end = start + timedelta(days=6)
    if start.year != end.year:
        label = f"{start:%b} {start.day}, {start.year} – {end:%b} {end.day}, {end.year}"
    else:
        label = f"{start:%b} {start.day} – {end:%b} {end.day}, {end.year}"
    return start, end, start - timedelta(days=7), start + timedelta(days=7), label


def _schedule_page(request, form=None):
    today = timezone.localdate()
    user_tasks = CareTask.objects.filter(plant__created_user=request.user)
    open_tasks = user_tasks.filter(completed_at__isnull=True)

    # Summary across all of the user's tasks, before filters.
    this_week = _week_start(today)
    stats = {
        "today": open_tasks.filter(due_date=today).count(),
        "week": open_tasks.filter(
            due_date__range=(this_week, this_week + timedelta(days=6))
        ).count(),
        "overdue": open_tasks.filter(due_date__lt=today).count(),
    }

    view = request.GET.get("view", "week")
    if view not in VIEWS:
        view = "week"
    anchor = _parse_date(request.GET.get("date"), today)

    plants = Plant.objects.filter(created_user=request.user).order_by("name")
    kind = request.GET.get("kind", "")
    if kind not in CareTask.Kind.values:
        kind = ""
    plant_id = request.GET.get("plant", "")
    if not (plant_id.isdigit() and plants.filter(pk=plant_id).exists()):
        plant_id = ""
    status = request.GET.get("status", "open")
    if status not in LIST_STATUSES:
        status = "open"

    tasks = user_tasks.select_related("plant", "plant__plant_species")
    if kind:
        tasks = tasks.filter(kind=kind)
    if plant_id:
        tasks = tasks.filter(plant_id=plant_id)

    # Calendar: every task (open and done) in the visible date range.
    weeks, range_label, prev_date, next_date = [], "", None, None
    if view != "list":
        start, end, prev_date, next_date, range_label = _calendar_range(view, anchor)
        by_day = {}
        for task in tasks.filter(due_date__range=(start, end)).order_by("completed_at", "plant__name"):
            by_day.setdefault(task.due_date, []).append(task)
        # Repeating tasks also appear on every later day they will come round.
        repeating = tasks.filter(
            completed_at__isnull=True, repeat_every_days__isnull=False, due_date__lte=end
        ).order_by("plant__name")
        for task in repeating:
            for day in _repeats(task, today, start, end):
                by_day.setdefault(day, []).append(_planned(task, day))
        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        cells = [{
            "date": day,
            "tasks": by_day.get(day, []),
            "is_today": day == today,
            "in_month": view == "week" or day.month == anchor.month,
        } for day in days]
        weeks = [cells[i:i + 7] for i in range(0, len(cells), 7)]

    # Task list: open tasks soonest first, completed ones most recent first.
    if status == "open":
        listed = tasks.filter(completed_at__isnull=True).order_by("due_date", "plant__name")
    elif status == "done":
        listed = tasks.filter(completed_at__isnull=False).order_by("-completed_at")
    else:
        listed = tasks.order_by("completed_at", "due_date", "plant__name")
    page = Paginator(listed, TASKS_PER_PAGE).get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    nav_params = request.GET.copy()
    for key in ("date", "page"):
        nav_params.pop(key, None)

    unplanned = _without_schedule(plants).count()

    if form is None:
        form = CareTaskForm(user=request.user, initial={"due_date": today.isoformat()})

    return render(request, "care/schedule.html", {
        "stats": stats,
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "view": view,
        "views": VIEWS.items(),
        "anchor": anchor,
        "weeks": weeks,
        "weekdays": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "range_label": range_label,
        "prev_date": prev_date,
        "next_date": next_date,
        "kind": kind,
        "kind_choices": CareTask.Kind.choices,
        "plant_id": plant_id,
        "plants": plants,
        "status": status,
        "status_choices": LIST_STATUSES.items(),
        "page": page,
        "query_string": params.urlencode(),
        "nav_query": nav_params.urlencode(),
        "is_filtered": bool(kind or plant_id),
        "unplanned": unplanned,
        "form": form,
        "show_form": form.is_bound,
        # Where the task actions send the user back to (kept across a failed add).
        "next_url": request.POST.get("next", "") if request.method == "POST" else request.get_full_path(),
    })


def _back(request):
    """Return to the page the action was sent from (same site only)."""
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                       require_https=request.is_secure()):
        return redirect(target)
    return redirect("care_schedule")


def _user_task(request, pk):
    # Only the owner of the plant can touch its tasks; others get a 404.
    return get_object_or_404(
        CareTask.objects.select_related("plant"), pk=pk, plant__created_user=request.user
    )


def schedule(request):
    return _schedule_page(request)


@require_POST
def task_add(request):
    form = CareTaskForm(request.POST, user=request.user)
    if not form.is_valid():
        return _schedule_page(request, form=form)
    task = form.save()
    messages.success(
        request, f"{task.get_kind_display()} for {task.plant.name} scheduled for {task.due_date:%b} {task.due_date.day}."
    )
    return _back(request)


@require_POST
def auto_plan(request):
    """Create a care schedule for every plant that has no open tasks yet."""
    plants = _without_schedule(
        Plant.objects.filter(created_user=request.user).select_related("plant_species")
    )
    planned = [plant.name for plant in plants if care_plan.apply(plant)]
    if planned:
        messages.success(request, f"Care schedule created for {len(planned)} plant{'s' if len(planned) != 1 else ''}: {', '.join(planned)}.")
    else:
        messages.success(request, "All your plants already have a care schedule.")
    return _back(request)


@require_POST
def task_complete(request, pk):
    task = _user_task(request, pk)
    if task.is_done:
        return _back(request)
    next_task = task.complete()
    message = f"{task.get_kind_display()} for {task.plant.name} marked as done."
    if next_task:
        message += f" Next one is due {next_task.due_date:%b} {next_task.due_date.day}."
    messages.success(request, message)
    return _back(request)


@require_POST
def task_delete(request, pk):
    task = _user_task(request, pk)
    task.delete()
    messages.success(request, f"{task.get_kind_display()} for {task.plant.name} was removed.")
    return _back(request)


def history(request):
    return render(request, "care/history.html")
