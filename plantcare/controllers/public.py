"""Public marketing pages."""
from django.shortcuts import render


def home(request):
    return render(request, "public/home.html")


def explore(request):
    return render(request, "public/explore.html")


def care_guides(request):
    return render(request, "public/care_guides.html")


def about(request):
    return render(request, "public/about.html")


def style_guide(request):
    return render(request, "dev/style_guide.html")
