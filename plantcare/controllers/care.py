"""Care schedules and history."""
from django.shortcuts import render


def schedule(request):
    return render(request, "care/schedule.html")


def watering(request):
    return render(request, "care/watering.html")


def history(request):
    return render(request, "care/history.html")
