"""Public marketing pages."""
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render


@login_not_required
def home(request):
    return render(request, "public/home.html")


@login_not_required
def explore(request):
    return render(request, "public/explore.html")


@login_not_required
def care_guides(request):
    return render(request, "public/care_guides.html")


@login_not_required
def about(request):
    return render(request, "public/about.html")


@login_not_required
def style_guide(request):
    return render(request, "dev/style_guide.html")
