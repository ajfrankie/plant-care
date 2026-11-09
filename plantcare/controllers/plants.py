"""The user's own plant collection."""
from django.shortcuts import render


def index(request):
    return render(request, "plants/list.html")


def add(request):
    return render(request, "plants/add.html")


def view(request):
    return render(request, "plants/view.html")


def edit(request):
    return render(request, "plants/edit.html")


def details(request):
    return render(request, "plants/details.html")


def health(request):
    return render(request, "plants/health.html")
