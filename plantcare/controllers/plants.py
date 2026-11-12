"""The user's own plant collection."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import PlantForm
from ..models import Plant

PER_PAGE = 8

SORTS = {
    "name": ("Name (A-Z)", ["name"]),
    "-name": ("Name (Z-A)", ["-name"]),
    "-created_at": ("Date Added (New)", ["-created_at"]),
    "created_at": ("Date Added (Old)", ["created_at"]),
    "-planting_date": ("Planting Date (New)", ["-planting_date", "name"]),
    "planting_date": ("Planting Date (Old)", ["planting_date", "name"]),
    "status": ("Status", ["status", "name"]),
}


def index(request):
    plants = (
        Plant.objects.filter(created_user=request.user)
        .select_related("plant_species")
        .annotate(last_care_at=Max("care_logs__performed_at"))
    )

    # Summary across the whole collection, before filters.
    all_plants = list(plants)
    stats = {
        "total": len(all_plants),
        "healthy": sum(p.status == Plant.Status.HEALTHY for p in all_plants),
        "due": sum(p.days_until_check <= 0 for p in all_plants),
        "attention": sum(p.status != Plant.Status.HEALTHY for p in all_plants),
    }

    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    sort = request.GET.get("sort", "name")
    if sort not in SORTS:
        sort = "name"

    if q:
        plants = plants.filter(
            Q(name__icontains=q)
            | Q(nickname__icontains=q)
            | Q(plant_species__common_name__icontains=q)
            | Q(plant_species__scientific_name__icontains=q)
        )
    if status in Plant.Status.values:
        plants = plants.filter(status=status)
    else:
        status = ""
    plants = plants.order_by(*SORTS[sort][1])

    page = Paginator(plants, PER_PAGE).get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "plants/list.html", {
        "page": page,
        "stats": stats,
        "q": q,
        "status": status,
        "sort": sort,
        "status_choices": Plant.Status.choices,
        "sort_choices": [(key, label) for key, (label, _) in SORTS.items()],
        "query_string": params.urlencode(),
        "is_filtered": bool(q or status),
    })


def add(request):
    form = PlantForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        plant = form.save(commit=False)
        plant.created_user = request.user
        plant.save()
        messages.success(request, f"{plant.name} was added to your plants.")
        return redirect("my_plants")

    return render(request, "plants/form.html", {"form": form})


def view(request):
    return render(request, "plants/view.html")


def edit(request, pk):
    # Only the user who created the plant can edit it; others get a 404.
    plant = get_object_or_404(Plant, pk=pk, created_user=request.user)
    old_image = plant.image.name
    # The form gets its own copy: validation writes submitted values onto the
    # instance, and the page header/current photo must keep showing saved data.
    form = PlantForm(
        request.POST or None, request.FILES or None,
        instance=Plant.objects.get(pk=plant.pk),
    )

    if request.method == "POST" and form.is_valid():
        updated = form.save()
        if old_image and updated.image.name != old_image:
            # Photo was replaced or removed: don't leave the old file behind.
            updated.image.storage.delete(old_image)
        messages.success(request, f"{updated.name} was updated.")
        return redirect("my_plants")

    return render(request, "plants/form.html", {"form": form, "plant": plant})


def details(request):
    return render(request, "plants/details.html")


def health(request):
    return render(request, "plants/health.html")
