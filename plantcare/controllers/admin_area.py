"""Admin-only pages: the care history of every user."""
import uuid
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from ..models import CareLog, User
from .dashboard import _require_admin
from .history import ACTIVITY_COLORS, PERIODS, _day_start

LOGS_PER_PAGE = 25
DEFAULT_PERIOD = "30d"


def _is_uuid(value):
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def care_history(request):
    """Every care log on the site, newest first, with filters."""
    _require_admin(request)
    today = timezone.localdate()

    activity = request.GET.get("activity", "")
    if activity not in CareLog.Activity.values:
        activity = ""
    period = request.GET.get("period", DEFAULT_PERIOD)
    if period not in PERIODS:
        period = DEFAULT_PERIOD
    owners = User.objects.filter(plants__care_logs__isnull=False).distinct().order_by("full_name")
    member_id = request.GET.get("user", "")
    if member_id and not (_is_uuid(member_id) and owners.filter(pk=member_id).exists()):
        member_id = ""
    q = request.GET.get("q", "").strip()

    logs = CareLog.objects.all()
    days = PERIODS[period][1]
    if days:
        logs = logs.filter(performed_at__gte=_day_start(today - timedelta(days=days - 1)))
    if member_id:
        logs = logs.filter(plant__created_user_id=member_id)
    if q:
        logs = logs.filter(Q(plant__name__icontains=q) | Q(notes__icontains=q))

    # Counts cover every activity; the activity filter only narrows the table.
    counts = dict(logs.values_list("activity").annotate(n=Count("id")).order_by())
    stats = [
        (key, label, counts.get(key, 0), ACTIVITY_COLORS[key])
        for key, label in CareLog.Activity.choices
    ]
    summary = logs.aggregate(
        total=Count("id"),
        plants=Count("plant", distinct=True),
        people=Count("plant__created_user", distinct=True),
    )
    if activity:
        logs = logs.filter(activity=activity)
    logs = logs.select_related("plant", "plant__created_user").order_by("-performed_at", "-pk")
    page = Paginator(logs, LOGS_PER_PAGE).get_page(request.GET.get("page"))
    for log in page.object_list:
        log.color = ACTIVITY_COLORS.get(log.activity, "var(--text-muted)")

    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "admin/care_history.html", {
        "page": page,
        "stats": stats,
        "summary": summary,
        "activity": activity,
        "period": period,
        "periods": [(key, label) for key, (label, _) in PERIODS.items()],
        "member_id": member_id,
        "owners": owners,
        "q": q,
        "is_filtered": bool(activity or member_id or q or period != DEFAULT_PERIOD),
        "query_string": params.urlencode(),
    })
