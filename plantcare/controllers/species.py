"""Manage the plant species that users can link their plants to."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import SpeciesForm
from ..models import PlantSpecies
from ..models.choices import Light

PER_PAGE = 8

SORTS = {
    "common_name": ("Name (A-Z)", ["common_name"]),
    "-common_name": ("Name (Z-A)", ["-common_name"]),
    "-created_at": ("Recently Added", ["-created_at"]),
    "created_at": ("Oldest First", ["created_at"]),
    "difficulty": ("Difficulty", ["difficulty", "common_name"]),
}


def index(request):
    species = PlantSpecies.objects.annotate(plant_count=Count("plants"))

    # Summary across the whole library, before filters.
    month_start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stats = {
        "total": species.count(),
        "indoor": species.filter(category=PlantSpecies.Category.INDOOR).count(),
        "outdoor": species.filter(category=PlantSpecies.Category.OUTDOOR).count(),
        "new": species.filter(created_at__gte=month_start).count(),
    }

    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    light = request.GET.get("light", "")
    sort = request.GET.get("sort", "common_name")
    if sort not in SORTS:
        sort = "common_name"

    if q:
        species = species.filter(
            Q(common_name__icontains=q)
            | Q(scientific_name__icontains=q)
            | Q(family__icontains=q)
        )
    if category in PlantSpecies.Category.values:
        species = species.filter(category=category)
    else:
        category = ""
    if light in Light.values:
        species = species.filter(light=light)
    else:
        light = ""
    species = species.order_by(*SORTS[sort][1])

    page = Paginator(species, PER_PAGE).get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "species/list.html", {
        "page": page,
        "stats": stats,
        "q": q,
        "category": category,
        "light": light,
        "sort": sort,
        "category_choices": PlantSpecies.Category.choices,
        "light_choices": Light.choices,
        "sort_choices": [(key, label) for key, (label, _) in SORTS.items()],
        "query_string": params.urlencode(),
        "is_filtered": bool(q or category or light),
    })


def add(request):
    form = SpeciesForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        species = form.save()
        messages.success(request, f"{species.common_name} was added to the species list.")
        return redirect("species")

    return render(request, "species/form.html", {"form": form})


def edit(request, pk):
    species = get_object_or_404(PlantSpecies, pk=pk)
    # The form gets its own copy so the page header keeps showing saved data
    # when validation fails.
    form = SpeciesForm(
        request.POST or None,
        instance=PlantSpecies.objects.get(pk=species.pk),
    )

    if request.method == "POST" and form.is_valid():
        updated = form.save()
        messages.success(request, f"{updated.common_name} was updated.")
        return redirect("species")

    return render(request, "species/form.html", {"form": form, "species": species})
