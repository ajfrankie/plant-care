from django.shortcuts import render
from django.utils import timezone


def _greeting(user):
    hour = timezone.localtime().hour
    if hour < 12:
        part = "morning"
    elif hour < 18:
        part = "afternoon"
    else:
        part = "evening"
    name = f", {user.first_name}" if user.first_name else ""
    return f"Good {part}{name} 🌿"


def index(request):
    return render(request, "dashboard/dashboard.html", {"greeting": _greeting(request.user)})
