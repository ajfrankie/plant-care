"""Sign-in, registration and per-user pages."""
from django.contrib import messages
from django.conf import settings as django_settings
from django.contrib.auth import REDIRECT_FIELD_NAME, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_not_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..forms import LoginForm, RegisterForm


def _safe_next(request):
    """The page to return to after signing in, if it is on this site."""
    next_url = request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(REDIRECT_FIELD_NAME, "")
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return ""


@login_not_required
def login(request):
    next_url = _safe_next(request)

    if request.user.is_authenticated:
        return redirect(next_url or django_settings.LOGIN_REDIRECT_URL)

    form = LoginForm(request.POST if request.method == "POST" else None)

    if form.is_valid():
        auth_login(request, form.user)
        if not form.cleaned_data["remember"]:
            request.session.set_expiry(0)  # ends when the browser closes
        return redirect(next_url or django_settings.LOGIN_REDIRECT_URL)

    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@login_not_required
@require_POST
def logout(request):
    auth_logout(request)
    return redirect("login")


@login_not_required
def register(request):
    form = RegisterForm(request.POST if request.method == "POST" else None)

    if form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:  # same email submitted twice at the same moment
            form.add_error("email", "An account with this email already exists.")
        else:
            messages.success(
                request,
                "Your account has been created. You can sign in once it has been activated.",
            )
            return redirect("login")

    return render(request, "accounts/register.html", {"form": form})


def settings(request):
    return render(request, "accounts/settings.html")


def notifications(request):
    return render(request, "accounts/notifications.html")
