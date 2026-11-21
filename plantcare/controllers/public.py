"""Public pages: home, the Plant Library, care guides and about."""
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render

from .. import health_library
from ..forms import ContactForm
from ..models import CareLog, Plant, PlantSpecies
from ..models.choices import SpecialFeature

LIBRARY_PER_PAGE = 12

# Plant Library filters: key -> (label, query). Categories come from the model;
# the last two are special features.
LIBRARY_FILTERS = {
    key: (label, Q(category=key)) for key, label in PlantSpecies.Category.choices
}
LIBRARY_FILTERS["pet_friendly"] = ("Pet Friendly", Q(special_features__contains=SpecialFeature.PET_FRIENDLY))
LIBRARY_FILTERS["easy"] = ("Easy Care", Q(difficulty__in=["very_easy", "easy"]))

LIBRARY_SORTS = {
    "name": ("Name (A-Z)", ["common_name"]),
    "popular": ("Most Popular", ["-plant_count", "common_name"]),
    "easiest": ("Easiest First", ["difficulty_rank", "common_name"]),
    "newest": ("Newest", ["-created_at"]),
}
DIFFICULTY_RANK = {key: i for i, key in enumerate(PlantSpecies.Difficulty.values)}

# Guide topics on the Care Guides page (key, label, icon name).
GUIDE_TOPICS = [
    ("watering", "Watering", "water"),
    ("light", "Light", "sun"),
    ("soil", "Soil", "sprout"),
    ("fertilizing", "Fertilizing", "flask"),
    ("pruning", "Pruning", "scissors"),
    ("propagation", "Propagation", "leaf"),
    ("pests", "Pests", "bug"),
    ("problems", "Problems A–Z", "health"),
    ("troubleshooting", "Troubleshooting", "tool"),
]


def _with_plant_counts(queryset):
    return queryset.annotate(plant_count=Count("plants"))


def _difficulty_rank():
    return Case(
        *[When(difficulty=key, then=Value(rank)) for key, rank in DIFFICULTY_RANK.items()],
        default=Value(len(DIFFICULTY_RANK)), output_field=IntegerField(),
    )


def _site_stats():
    return {
        "species": PlantSpecies.objects.count(),
        "plants": Plant.objects.count(),
        "care_logs": CareLog.objects.count(),
        "problems": len(health_library.ISSUES),
    }


@login_not_required
def home(request):
    popular = list(
        _with_plant_counts(PlantSpecies.objects.all()).order_by("-plant_count", "common_name")[:8]
    )
    return render(request, "public/home.html", {
        "popular": popular,
        "stats": _site_stats(),
        "guide_topics": GUIDE_TOPICS,
    })


@login_not_required
def explore(request):
    species = _with_plant_counts(PlantSpecies.objects.all()).annotate(difficulty_rank=_difficulty_rank())
    total = species.count()

    q = request.GET.get("q", "").strip()
    show = request.GET.get("show", "")
    if show not in LIBRARY_FILTERS:
        show = ""
    sort = request.GET.get("sort", "name")
    if sort not in LIBRARY_SORTS:
        sort = "name"

    # Counts for every filter tab, so empty ones can be hidden.
    counts = PlantSpecies.objects.aggregate(**{
        key: Count("pk", filter=query) for key, (_, query) in LIBRARY_FILTERS.items()
    })
    filters = [(key, label, counts[key]) for key, (label, _) in LIBRARY_FILTERS.items() if counts[key]]

    if q:
        species = species.filter(
            Q(common_name__icontains=q) | Q(scientific_name__icontains=q)
            | Q(family__icontains=q) | Q(description__icontains=q)
        )
    if show:
        species = species.filter(LIBRARY_FILTERS[show][1])
    species = species.order_by(*LIBRARY_SORTS[sort][1])

    page = Paginator(species, LIBRARY_PER_PAGE).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "public/explore.html", {
        "page": page,
        "total": total,
        "q": q,
        "show": show,
        "sort": sort,
        "filters": filters,
        "sort_choices": [(key, label) for key, (label, _) in LIBRARY_SORTS.items()],
        "query_string": params.urlencode(),
        "is_filtered": bool(q or show),
    })


@login_not_required
def species_detail(request, pk):
    species = get_object_or_404(_with_plant_counts(PlantSpecies.objects.all()), pk=pk)
    related = list(
        PlantSpecies.objects.filter(category=species.category).exclude(pk=species.pk)
        .order_by("common_name")[:4]
    )
    return render(request, "public/species.html", {"species": species, "related": related})


@login_not_required
def care_guides(request):
    topic = request.GET.get("topic", "watering")
    if topic not in {key for key, _, _ in GUIDE_TOPICS}:
        topic = "watering"
    problems = sorted(
        ({"key": key, **issue} for key, issue in health_library.ISSUES.items()),
        key=lambda issue: (issue["type"], issue["name"]),
    )
    return render(request, "public/care_guides.html", {
        "topics": GUIDE_TOPICS,
        "topic": topic,
        "problems": problems,
        "problem_types": sorted({issue["type"] for issue in problems}),
    })


@login_not_required
def about(request):
    initial = {}
    if request.user.is_authenticated:
        initial = {"name": request.user.full_name, "email": request.user.email}
    form = ContactForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if not form.cleaned_data.get("website"):  # filled in only by bots
            form.save()
        messages.success(request, "Thanks for your message! We'll get back to you soon.")
        return redirect(f"{request.path}#contact")
    return render(request, "public/about.html", {"form": form, "stats": _site_stats()})


@login_not_required
def style_guide(request):
    return render(request, "dev/style_guide.html")
