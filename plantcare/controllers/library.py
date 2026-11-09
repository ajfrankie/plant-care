"""The shared plant species library."""
from django.shortcuts import render


def index(request):
    return render(request, "library/list.html")


def create(request):
    return render(request, "library/create.html")


def view(request):
    return render(request, "library/view.html")


def edit(request):
    return render(request, "library/edit.html")
