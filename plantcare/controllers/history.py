"""Care history: a timeline of everything done to the user's plants."""
import csv
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Window
from django.db.models.functions import RowNumber
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..forms import CareLogForm
from ..models import CareLog, Plant

LOGS_PER_PAGE = 20
LOGS_PER_PLANT = 10  # latest entries shown in each plant's section of the all-plants view

# key: (label, days back including today; None = all time)
PERIODS = {
    "7d": ("Last 7 Days", 7),
    "30d": ("Last 30 Days", 30),
    "90d": ("Last 90 Days", 90),
    "1y": ("Last 12 Months", 365),
    "all": ("All Time", None),
}
DEFAULT_PERIOD = "all"

# Colour used for each activity on the chart and the timeline.
ACTIVITY_COLORS = {
    CareLog.Activity.WATERING: "var(--info)",
    CareLog.Activity.FERTILIZING: "var(--success)",
    CareLog.Activity.MAINTENANCE: "var(--primary)",
    CareLog.Activity.HEALTH: "var(--warning)",
    CareLog.Activity.NOTE: "var(--text-muted)",
}


def _day_start(day):
    """The first moment of ``day`` in the current time zone."""
    return timezone.make_aware(datetime.combine(day, time.min))


def _month_add(day, months):
    """First of the month ``months`` after the month of ``day``."""
    index = day.year * 12 + day.month - 1 + months
    return day.replace(year=index // 12, month=index % 12 + 1, day=1)


def _filters(request, plants):
    """(activity, plant id, period) from the query string, invalid values dropped."""
    activity = request.GET.get("activity", "")
    if activity not in CareLog.Activity.values:
        activity = ""
    plant_id = request.GET.get("plant", "")
    if not (plant_id.isdigit() and plants.filter(pk=plant_id).exists()):
        plant_id = ""
    period = request.GET.get("period", DEFAULT_PERIOD)
    if period not in PERIODS:
        period = DEFAULT_PERIOD
    return activity, plant_id, period


def _filtered_logs(user, activity, plant_id, period, today):
    logs = CareLog.objects.filter(plant__created_user=user)
    if plant_id:
        logs = logs.filter(plant_id=plant_id)
    days = PERIODS[period][1]
    if days:
        logs = logs.filter(performed_at__gte=_day_start(today - timedelta(days=days - 1)))
    if activity:
        logs = logs.filter(activity=activity)
    return logs


def _chart(logs, period, today):
    """Bars of activity counts, one per day, week or month depending on the period.

    Each bar is split by activity so the colours match the timeline.
    """
    days = PERIODS[period][1]
    if days and days <= 30:
        starts = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
        step = "day"
    elif days and days <= 90:
        # Weeks ending today: the last bar covers today and the 6 days before.
        count = -(-days // 7)
        starts = [today - timedelta(days=7 * i + 6) for i in range(count - 1, -1, -1)]
        step = "week"
    else:
        this_month = today.replace(day=1)
        starts = [_month_add(this_month, -i) for i in range(11, -1, -1)]
        step = "month"

    def bucket_of(day):
        if step == "day":
            return day
        if step == "week":
            return today - timedelta(days=(today - day).days // 7 * 7 + 6)
        return day.replace(day=1)

    counts = {start: {} for start in starts}
    rows = logs.filter(performed_at__gte=_day_start(starts[0])).values_list("performed_at", "activity")
    for performed_at, activity in rows:
        bucket = counts.get(bucket_of(timezone.localdate(performed_at)))
        if bucket is not None:
            bucket[activity] = bucket.get(activity, 0) + 1

    peak = max((sum(c.values()) for c in counts.values()), default=0) or 1
    labels = dict(CareLog.Activity.choices)
    bars = []
    for start in starts:
        by_activity = counts[start]
        total = sum(by_activity.values())
        if step == "day":
            label = "Today" if start == today else (f"{start:%a}" if days <= 7 else f"{start.day}")
            title = f"{start:%a}, {start:%b} {start.day}"
        elif step == "week":
            end = min(start + timedelta(days=6), today)
            label = f"{start:%b} {start.day}"
            title = f"{start:%b} {start.day} – {end:%b} {end.day}"
        else:
            label = f"{start:%b}"
            title = f"{start:%B %Y}"
        bars.append({
            "label": label,
            "title": f"{title}: {total} activit{'y' if total == 1 else 'ies'}",
            "is_current": start == bucket_of(today),
            "height": round(total / peak * 100),
            "segments": [
                {"activity": key, "label": labels[key], "count": by_activity[key],
                 "share": round(by_activity[key] / total * 100, 1), "color": ACTIVITY_COLORS[key]}
                for key in CareLog.Activity.values if by_activity.get(key)
            ],
        })
    return {
        "bars": bars,
        "total": sum(sum(c.values()) for c in counts.values()),
        # Show every label on short charts, every few on long ones.
        "label_every": 1 if len(bars) <= 14 else 5,
        "step": step,
    }


def _colour(logs):
    for log in logs:
        log.color = ACTIVITY_COLORS.get(log.activity, "var(--text-muted)")


def _plant_groups(logs):
    """Each plant with history, most recently cared for first, with its latest entries."""
    totals = {
        row["plant_id"]: row
        for row in logs.values("plant_id").annotate(n=Count("id"), last=Max("performed_at")).order_by()
    }
    if not totals:
        return []
    ranked = logs.annotate(
        row=Window(RowNumber(), partition_by=[F("plant_id")], order_by=[F("performed_at").desc(), F("pk").desc()])
    ).filter(row__lte=LOGS_PER_PLANT)
    recent = {}
    for log in ranked:
        recent.setdefault(log.plant_id, []).append(log)
    groups = []
    for plant_id, entries in recent.items():
        _colour(entries)
        total = totals[plant_id]["n"]
        groups.append({
            "plant": entries[0].plant,
            "logs": entries,
            "total": total,
            "more": total - len(entries),
            "last": totals[plant_id]["last"],
        })
    groups.sort(key=lambda g: g["last"], reverse=True)
    return groups


def _history_page(request, form=None):
    today = timezone.localdate()
    plants = Plant.objects.filter(created_user=request.user).order_by("name")
    activity, plant_id, period = _filters(request, plants)

    # Stats and chart cover every activity type (the activity filter only narrows the timeline).
    in_scope = _filtered_logs(request.user, "", plant_id, period, today)
    counts = dict(in_scope.values_list("activity").annotate(n=Count("id")).order_by())
    stats = {key: counts.get(key, 0) for key in CareLog.Activity.values}

    logs = in_scope.filter(activity=activity) if activity else in_scope
    logs = logs.select_related("plant", "plant__plant_species").order_by("-performed_at", "-pk")
    if plant_id:
        # One plant chosen: its full timeline, page by page.
        page, groups = Paginator(logs, LOGS_PER_PAGE).get_page(request.GET.get("page")), []
        _colour(page.object_list)
    else:
        # All plants: one collapsible timeline per plant.
        page, groups = None, _plant_groups(logs)

    params = request.GET.copy()
    params.pop("page", None)
    group_params = params.copy()  # links that open one plant's timeline
    group_params.pop("plant", None)

    if form is None:
        form = CareLogForm(user=request.user, initial={
            "plant": plant_id or None,
            "activity": activity or CareLog.Activity.WATERING,
            "performed_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        })

    return render(request, "care/history.html", {
        "today": today,
        "today_key": today.isoformat(),
        "yesterday_key": (today - timedelta(days=1)).isoformat(),
        "now_local": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        "stats": stats,
        "chart": _chart(in_scope, period, today),
        "legend": [(key, label, ACTIVITY_COLORS[key]) for key, label in CareLog.Activity.choices],
        "activity": activity,
        "activity_choices": CareLog.Activity.choices,
        "plant_id": plant_id,
        "plants": plants,
        "period": period,
        "period_label": PERIODS[period][0],
        "periods": [(key, label) for key, (label, _) in PERIODS.items()],
        "is_filtered": bool(activity or plant_id or period != DEFAULT_PERIOD),
        "page": page,
        "groups": groups,
        "is_empty": not (page.object_list if page else groups),
        "query_string": params.urlencode(),
        "group_query": group_params.urlencode(),
        "form": form,
        "show_form": form.is_bound,
        "next_url": request.POST.get("next", "") if request.method == "POST" else request.get_full_path(),
    })


def _back(request):
    """Return to the page the action was sent from (same site only)."""
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                       require_https=request.is_secure()):
        return redirect(target)
    return redirect("care_history")


def index(request):
    return _history_page(request)


@require_POST
def add(request):
    form = CareLogForm(request.POST, user=request.user)
    if not form.is_valid():
        return _history_page(request, form=form)
    log = form.save()
    messages.success(request, f"{log.get_activity_display()} for {log.plant.name} added to the history.")
    return _back(request)


@require_POST
def delete(request, pk):
    # Only the owner of the plant can remove its history; others get a 404.
    log = get_object_or_404(CareLog.objects.select_related("plant"), pk=pk, plant__created_user=request.user)
    log.delete()
    messages.success(request, f"{log.get_activity_display()} for {log.plant.name} was removed from the history.")
    return _back(request)


def export(request):
    """The filtered history as a CSV file."""
    today = timezone.localdate()
    plants = Plant.objects.filter(created_user=request.user)
    activity, plant_id, period = _filters(request, plants)
    logs = (
        _filtered_logs(request.user, activity, plant_id, period, today)
        .select_related("plant", "plant__plant_species")
        .order_by("-performed_at", "-pk")
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="care-history-{today.isoformat()}.csv"'
    response.write("﻿")  # so spreadsheet apps read it as UTF-8
    writer = csv.writer(response)
    writer.writerow(["Date", "Time", "Plant", "Species", "Activity", "Notes"])
    for log in logs.iterator():
        when = timezone.localtime(log.performed_at)
        species = log.plant.plant_species
        writer.writerow([
            when.date().isoformat(), when.strftime("%H:%M"), _safe_cell(log.plant.name),
            _safe_cell(species.scientific_name if species else ""),
            log.get_activity_display(), _safe_cell(log.notes),
        ])
    return response


def _safe_cell(value):
    """Stop spreadsheet apps treating user text as a formula."""
    if value and value[0] in "=+-@\t\r":
        return "'" + value
    return value
