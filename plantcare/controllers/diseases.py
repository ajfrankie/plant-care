"""Diseases & Pests: look up a problem you already recognise and get its organic cure.

Everyone can browse the library; admins can also add, edit and delete entries.
"""
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .. import health_library
from ..forms import PlantIssueForm
from ..models import HealthCase, PlantIssue
from .dashboard import _require_admin

# Display order of the problem types, and the badge style for each.
TYPE_BADGES = {
    PlantIssue.Type.PEST: "badge-warning",
    PlantIssue.Type.FUNGAL: "badge-error",
    PlantIssue.Type.BACTERIAL: "badge-error",
    PlantIssue.Type.VIRAL: "badge-error",
    PlantIssue.Type.CARE: "badge-info",
}


def index(request):
    q = request.GET.get("q", "").strip()
    kind = request.GET.get("type", "")
    library = list(PlantIssue.objects.all())
    present = {issue.type for issue in library}
    types = [t for t in PlantIssue.Type.values if t in present]
    if kind not in types:
        kind = ""

    # Plants being treated for each problem right now: the user's own, or everyone's for admins.
    cases = HealthCase.objects.exclude(status=HealthCase.Status.RESOLVED).exclude(issue_key="")
    if not request.user.is_staff:
        cases = cases.filter(plant__created_user=request.user)
    affected = dict(cases.values_list("issue_key").annotate(n=Count("plant", distinct=True)).order_by())

    needle = q.lower()
    issues = []
    for issue in library:
        if kind and issue.type != kind:
            continue
        if needle and not any(needle in value.lower() for value in (issue.name, issue.symptoms, issue.type)):
            continue
        issues.append({
            **issue.as_dict(),
            "pk": issue.pk,
            "key": issue.key,
            "badge": TYPE_BADGES.get(issue.type, "badge-info"),
            "affected": affected.get(issue.key, 0),
            "treatments": [t for t in issue.treatments if health_library.is_organic(t)],
        })
    issues.sort(key=lambda i: (-i["affected"], i["name"]))

    counts = {t: 0 for t in types}
    for issue in library:
        counts[issue.type] += 1

    return render(request, "plants/diseases.html", {
        "issues": issues,
        "q": q,
        "type": kind,
        "types": [(t, counts[t]) for t in types],
        "total": len(library),
        "open_key": request.GET.get("open", ""),
    })


def add(request):
    _require_admin(request)
    form = PlantIssueForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        issue = form.save()
        messages.success(request, f"{issue.name} was added to Diseases & Pests.")
        return redirect(f"{_list_url()}?open={issue.key}#issue-{issue.key}")
    return render(request, "plants/disease_form.html", {"form": form})


def edit(request, pk):
    _require_admin(request)
    issue = get_object_or_404(PlantIssue, pk=pk)
    form = PlantIssueForm(request.POST or None, instance=PlantIssue.objects.get(pk=pk))
    if request.method == "POST" and form.is_valid():
        issue = form.save()
        messages.success(request, f"{issue.name} was updated.")
        return redirect(f"{_list_url()}?open={issue.key}#issue-{issue.key}")
    in_use = HealthCase.objects.filter(issue_key=issue.key).count()
    return render(request, "plants/disease_form.html", {"form": form, "issue": issue, "in_use": in_use})


@require_POST
def delete(request, pk):
    _require_admin(request)
    issue = get_object_or_404(PlantIssue, pk=pk)
    issue.delete()  # health cases keep their own title, so nothing else breaks
    messages.success(request, f"{issue.name} was removed from Diseases & Pests.")
    return redirect("diseases")


def _list_url():
    from django.urls import reverse
    return reverse("diseases")
