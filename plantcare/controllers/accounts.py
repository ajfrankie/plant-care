"""Sign-in, registration and per-user pages."""
from django.shortcuts import render


def login(request):
    return render(request, "accounts/login.html")


def register(request):
    return render(request, "accounts/register.html")


def settings(request):
    return render(request, "accounts/settings.html")


def notifications(request):
    return render(request, "accounts/notifications.html")
