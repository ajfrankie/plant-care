"""Plant health: photo checks, problem diagnosis, organic treatments and follow-up tracking."""
import logging
from contextlib import nullcontext
from datetime import timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import health_ai, health_library
from ..forms import HealthCheckForm, HealthUpdateForm
from ..models import CareLog, HealthCase, HealthCheck, Plant
from ..models.health import sync_plant_status

logger = logging.getLogger(__name__)

STATUS_FILTERS = {"open": "Open Cases", "resolved": "Resolved", "all": "All Cases"}
SEVERITY_FROM_OVERALL = {"healthy": "mild", "mild": "mild", "moderate": "moderate", "severe": "severe"}


def _user_cases(request):
    return HealthCase.objects.filter(plant__created_user=request.user).select_related(
        "plant", "plant__plant_species"
    )


def _issue_title(key, fallback=""):
    entry = health_library.get(key)
    return entry["name"] if entry else (fallback or "Unidentified issue")


def _log(plant, notes):
    CareLog.objects.create(
        plant=plant, activity=CareLog.Activity.HEALTH, performed_at=timezone.now(), notes=notes[:500]
    )


def index(request, form=None):
    today = timezone.localdate()
    cases = _user_cases(request).prefetch_related("checks")
    open_cases = cases.exclude(status=HealthCase.Status.RESOLVED)

    status = request.GET.get("status", "open")
    if status not in STATUS_FILTERS:
        status = "open"
    listed = {"open": open_cases, "resolved": cases.filter(status=HealthCase.Status.RESOLVED),
              "all": cases}[status]

    plants = (
        Plant.objects.filter(created_user=request.user)
        .select_related("plant_species")
        .annotate(open_cases=Count("health_cases", filter=~Q(health_cases__status=HealthCase.Status.RESOLVED)))
        .order_by("name")
    )
    stats = {
        "open": open_cases.count(),
        "due": open_cases.filter(next_check_date__lte=today).count(),
        "resolved": cases.filter(status=HealthCase.Status.RESOLVED).count(),
        "healthy": sum(1 for p in plants if not p.open_cases),
    }

    if form is None:
        initial = {}
        if request.GET.get("plant", "").isdigit():
            initial["plant"] = request.GET["plant"]
        form = HealthCheckForm(user=request.user, initial=initial)

    return render(request, "plants/health.html", {
        "today": today,
        "stats": stats,
        "cases": list(listed.order_by("next_check_date") if status == "open" else listed),
        "due_cases": list(open_cases.filter(next_check_date__lte=today).order_by("next_check_date")),
        "status": status,
        "status_choices": STATUS_FILTERS.items(),
        "plants": plants,
        "healthy_checks": HealthCheck.objects.filter(
            plant__created_user=request.user, case__isnull=True
        ).select_related("plant")[:6],
        "form": form,
        "show_form": form.is_bound or "new" in request.GET,
        "library": health_library.ISSUES,
    })


@require_POST
def new_check(request):
    form = HealthCheckForm(request.POST, request.FILES, user=request.user)
    if not form.is_valid():
        return index(request, form=form)

    data = form.cleaned_data
    plant = data["plant"]
    image = data["image"]
    today = timezone.localdate()

    result, error = None, ""
    if data["action"] == HealthCheckForm.FIND:
        try:
            result = health_ai.analyse(image, plant=plant, notes=data["notes"])
        except health_ai.AnalysisError as exc:
            error = str(exc)

    with transaction.atomic():
        check = HealthCheck(
            plant=plant, image=image, notes=data["notes"],
            analysis=result or {},
            analysis_status=(HealthCheck.Analysis.DONE if result else
                             HealthCheck.Analysis.FAILED if error else HealthCheck.Analysis.SKIPPED),
            analysis_error=error,
        )

        if result and not result["issues"]:
            # Nothing wrong found: keep the photo as a healthy check, no case to track.
            check.save()
            _log(plant, f"Health check: looks healthy. {result['summary']}")
            sync_plant_status(plant)
            messages.success(request, f"Good news — {plant.name} looks healthy. {result['summary']}")
            return redirect("plant_health")

        if data["action"] == HealthCheckForm.KNOWN:
            key = data["issue_key"]
            title = _issue_title(key, data["other_issue"])
            severity, source = data["severity"], HealthCase.Source.USER
        elif result:
            top = result["issues"][0]
            key = top["key"] if top["key"] in health_library.ISSUES else ""
            title = _issue_title(key, top["name"])
            severity, source = SEVERITY_FROM_OVERALL[result["overall"]], HealthCase.Source.AI
        else:
            key, title = "", "Unidentified issue"
            severity, source = data["severity"], HealthCase.Source.UNKNOWN

        case = HealthCase.objects.create(
            plant=plant, title=title[:120], issue_key=key, severity=severity, source=source,
            check_every_days=data["check_every_days"],
            next_check_date=today + timedelta(days=data["check_every_days"]),
        )
        check.case = case
        check.save()
        case.schedule_next_check(today)
        _log(plant, f"Health check started: {title}")
        sync_plant_status(plant)

    if error:
        messages.error(request, f"{error} You can choose the issue yourself below.")
    else:
        messages.success(request, f"Tracking {title} on {plant.name}. Next photo update: "
                                  f"{case.next_check_date:%b} {case.next_check_date.day}.")
    return redirect("health_case", pk=case.pk)


def _treatments(case, latest):
    """Library treatments for the case's issue, plus any extra ones the analysis suggested."""
    treatments, seen = [], set()
    entry = case.library_entry
    for item in (entry["treatments"] if entry else []):
        treatments.append(item)
        seen.add(item["name"].lower())
    analysis = latest.analysis if latest else {}
    for issue in analysis.get("issues", []):
        if issue["key"] == case.issue_key or (not case.issue_key and issue["name"] == case.title):
            for item in issue["organic_treatments"]:
                if item["name"].lower() not in seen:
                    treatments.append({**item, "suggested": True})
                    seen.add(item["name"].lower())
    return treatments


def case_detail(request, pk, form=None):
    case = get_object_or_404(_user_cases(request), pk=pk)
    checks = list(case.checks.order_by("created_at"))
    latest = checks[-1] if checks else None
    analysed = next((c for c in reversed(checks) if c.analysis_status == HealthCheck.Analysis.DONE), None)
    analysis = analysed.analysis if analysed else {}
    entry = case.library_entry
    return render(request, "plants/health_case.html", {
        "case": case,
        "checks": checks,
        "latest": latest,
        "analysis": analysis,
        "other_issues": [i for i in analysis.get("issues", [])
                         if i["key"] != case.issue_key and i["name"] != case.title],
        "entry": entry,
        "treatments": _treatments(case, analysed),
        "prevention": entry["prevention"] if entry else next(
            (i["prevention"] for i in analysis.get("issues", []) if i["name"] == case.title), ""),
        "form": form or HealthUpdateForm(),
        "issue_choices": health_library.CHOICES,
        "severity_choices": HealthCase.Severity.choices,
        "today": timezone.localdate(),
    })


@require_POST
def case_update(request, pk):
    case = get_object_or_404(_user_cases(request), pk=pk)
    form = HealthUpdateForm(request.POST, request.FILES)
    if not form.is_valid():
        return case_detail(request, pk, form=form)

    data = form.cleaned_data
    previous = case.latest_check
    result, error = None, ""
    if data["analyse"]:
        try:
            # Open the earlier photo only for the analysis and close it right after:
            # a file left open can't be deleted on Windows.
            with (previous.image.open("rb") if previous else nullcontext()) as earlier:
                result = health_ai.analyse(
                    data["image"], plant=case.plant, notes=data["notes"],
                    previous_image=earlier, previous_title=case.title,
                )
        except health_ai.AnalysisError as exc:
            error = str(exc)

    progress = data["progress"] or (result or {}).get("progress") or HealthCheck.Progress.SAME
    if progress == HealthCheck.Progress.FIRST:
        progress = HealthCheck.Progress.SAME

    with transaction.atomic():
        HealthCheck.objects.create(
            plant=case.plant, case=case, image=data["image"], notes=data["notes"],
            progress=progress, analysis=result or {}, analysis_error=error,
            analysis_status=(HealthCheck.Analysis.DONE if result else
                             HealthCheck.Analysis.FAILED if error else HealthCheck.Analysis.SKIPPED),
        )
        case.status = (HealthCase.Status.IMPROVING if progress == HealthCheck.Progress.BETTER
                       else HealthCase.Status.ACTIVE)
        if result and result["issues"]:
            case.severity = SEVERITY_FROM_OVERALL[result["overall"]]
        case.save(update_fields=["status", "severity"])
        case.schedule_next_check()
        _log(case.plant, f"Health photo update ({HealthCheck.Progress(progress).label.lower()}): {case.title}")
        sync_plant_status(case.plant)

    if error:
        messages.error(request, f"Photo saved, but {error[0].lower()}{error[1:]}")
    elif result and not result["issues"]:
        messages.success(request, "The new photo looks healthy! If you agree, mark this case as resolved.")
    else:
        messages.success(request, f"Photo update saved. Next update due "
                                  f"{case.next_check_date:%b} {case.next_check_date.day}.")
    return redirect("health_case", pk=case.pk)


@require_POST
def case_set_issue(request, pk):
    case = get_object_or_404(_user_cases(request), pk=pk)
    key = request.POST.get("issue_key", "")
    other = request.POST.get("other_issue", "").strip()[:120]
    severity = request.POST.get("severity", "")
    if key not in health_library.ISSUES:
        key = ""
    if not (key or other):
        messages.error(request, "Choose an issue from the list or type one in.")
        return redirect("health_case", pk=case.pk)
    case.issue_key = key
    case.title = _issue_title(key, other)
    case.source = HealthCase.Source.USER
    if severity in HealthCase.Severity.values:
        case.severity = severity
    case.save(update_fields=["issue_key", "title", "source", "severity"])
    sync_plant_status(case.plant)
    messages.success(request, f"Issue set to {case.title}.")
    return redirect("health_case", pk=case.pk)


@require_POST
def case_reanalyse(request, pk):
    case = get_object_or_404(_user_cases(request), pk=pk)
    check = case.latest_check
    if check is None:
        return redirect("health_case", pk=case.pk)
    try:
        with check.image.open("rb") as image:
            result = health_ai.analyse(image, plant=case.plant, notes=check.notes)
    except health_ai.AnalysisError as exc:
        check.analysis_status, check.analysis_error = HealthCheck.Analysis.FAILED, str(exc)
        check.save(update_fields=["analysis_status", "analysis_error"])
        messages.error(request, str(exc))
        return redirect("health_case", pk=case.pk)

    check.analysis, check.analysis_status, check.analysis_error = result, HealthCheck.Analysis.DONE, ""
    check.save(update_fields=["analysis", "analysis_status", "analysis_error"])
    if result["issues"] and case.source == HealthCase.Source.UNKNOWN:
        top = result["issues"][0]
        case.issue_key = top["key"] if top["key"] in health_library.ISSUES else ""
        case.title = _issue_title(case.issue_key, top["name"])[:120]
        case.severity = SEVERITY_FROM_OVERALL[result["overall"]]
        case.source = HealthCase.Source.AI
        case.save(update_fields=["issue_key", "title", "severity", "source"])
        sync_plant_status(case.plant)
    messages.success(request, result["summary"] or "Photo analysed.")
    return redirect("health_case", pk=case.pk)


@require_POST
def case_resolve(request, pk):
    case = get_object_or_404(_user_cases(request), pk=pk)
    if case.is_open:
        case.resolve()
        messages.success(request, f"{case.title} on {case.plant.name} marked as resolved. 🌿")
    else:
        case.reopen()
        messages.success(request, f"{case.title} on {case.plant.name} reopened.")
    return redirect("health_case", pk=case.pk)


@require_POST
def case_frequency(request, pk):
    case = get_object_or_404(_user_cases(request), pk=pk)
    days = request.POST.get("check_every_days", "")
    if not (days.isdigit() and 1 <= int(days) <= 60):
        messages.error(request, "Choose between 1 and 60 days.")
        return redirect("health_case", pk=case.pk)
    case.check_every_days = int(days)
    case.save(update_fields=["check_every_days"])
    latest = case.latest_check
    if case.is_open:
        case.schedule_next_check(timezone.localdate(latest.created_at) if latest else None)
    messages.success(request, f"Photo updates every {case.check_every_days} days. "
                              f"Next: {case.next_check_date:%b} {case.next_check_date.day}.")
    return redirect("health_case", pk=case.pk)


@require_POST
def case_delete(request, pk):
    case = get_object_or_404(_user_cases(request), pk=pk)
    plant, title = case.plant, case.title
    images = [c.image for c in case.checks.all() if c.image]
    with transaction.atomic():
        if not plant.health_cases.exclude(pk=case.pk).exclude(status=HealthCase.Status.RESOLVED).exists():
            case._clear_reminders()
        case.delete()
        sync_plant_status(plant)
    for image in images:
        try:
            image.storage.delete(image.name)
        except OSError:
            # e.g. the file is open in another program on Windows. The case is
            # already gone; leaving one stray photo behind is better than an error page.
            logger.warning("Could not delete health photo %s", image.name, exc_info=True)
    messages.success(request, f"Health case {title} for {plant.name} was deleted.")
    return redirect("plant_health")
