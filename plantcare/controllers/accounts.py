"""Sign-in, registration and per-user pages."""
import json

from django.contrib import messages
from django.conf import settings as django_settings
from django.contrib.auth import (
    REDIRECT_FIELD_NAME, login as auth_login, logout as auth_logout, update_session_auth_hash,
)
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..forms import (
    CarePreferencesForm, DeleteAccountForm, LoginForm, NotificationPreferencesForm, ProfileForm,
    RegisterForm,
)
from ..models import CareLog, CareTask, HealthCase, HealthCheck, Notification, Plant, User, WaterReminder


def _safe_next(request):
    """The page to return to after signing in, if it is on this site."""
    next_url = request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(REDIRECT_FIELD_NAME, "")
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return ""


def _home(user):
    """Where a user lands after signing in: admins get the admin dashboard."""
    return "admin_dashboard" if user.is_staff else django_settings.LOGIN_REDIRECT_URL


@login_not_required
def login(request):
    next_url = _safe_next(request)

    if request.user.is_authenticated:
        return redirect(next_url or _home(request.user))

    form = LoginForm(request.POST if request.method == "POST" else None)

    if form.is_valid():
        auth_login(request, form.user)
        if not form.cleaned_data["remember"]:
            request.session.set_expiry(0)  # ends when the browser closes
        return redirect(next_url or _home(form.user))

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


# Settings page tabs, and which form each one posts.
SETTINGS_TABS = ["account", "notifications", "care", "security", "privacy", "about"]
SETTINGS_FORMS = {
    "account": (ProfileForm, "Your account details were saved."),
    "notifications": (NotificationPreferencesForm, "Your notification preferences were saved."),
    "care": (CarePreferencesForm, "Your care preferences were saved."),
}


def _settings_url(tab):
    return f"{reverse('settings')}?tab={tab}"


def settings(request):
    user = request.user
    tab = request.POST.get("tab") or request.GET.get("tab", "")
    if tab not in SETTINGS_TABS:
        tab = "account"

    # Each tab's form shows the saved values, except the one just posted.
    forms = {name: form_class(instance=user) for name, (form_class, _) in SETTINGS_FORMS.items()}
    forms["security"] = PasswordChangeForm(user)
    forms["privacy"] = DeleteAccountForm(user=user)

    if request.method == "POST":
        if tab in SETTINGS_FORMS:
            form_class, done = SETTINGS_FORMS[tab]
            # A copy, so a rejected form does not change the user shown elsewhere on the page.
            form = form_class(request.POST, request.FILES, instance=User.objects.get(pk=user.pk))
            if form.is_valid():
                try:
                    with transaction.atomic():
                        form.save()
                except IntegrityError:  # same email taken at the same moment
                    form.add_error("email", "An account with this email already exists.")
                else:
                    messages.success(request, done)
                    return redirect(_settings_url(tab))
            forms[tab] = form
        elif tab == "security":
            form = PasswordChangeForm(user, request.POST)
            if form.is_valid():
                form.save()
                update_session_auth_hash(request, form.user)  # stay signed in
                messages.success(request, "Your password was changed.")
                return redirect(_settings_url(tab))
            forms[tab] = form

    return render(request, "accounts/settings.html", {
        "tab": tab,
        "profile_form": forms["account"],
        "notification_form": forms["notifications"],
        "care_form": forms["care"],
        "password_form": forms["security"],
        "delete_form": forms["privacy"],
        "data_counts": _data_counts(user),
    })


def _data_counts(user):
    plants = Plant.objects.filter(created_user=user)
    return {
        "plants": plants.count(),
        "tasks": CareTask.objects.filter(plant__in=plants).count(),
        "logs": CareLog.objects.filter(plant__in=plants).count(),
        "health_cases": HealthCase.objects.filter(plant__in=plants).count(),
    }


def _rows(queryset, exclude=()):
    """Plain dicts of a queryset's field values, for the data export."""
    rows = []
    for obj in queryset:
        row = {}
        for field in obj._meta.concrete_fields:
            if field.name in exclude:
                continue
            value = field.value_from_object(obj)
            if hasattr(value, "name"):  # file fields
                value = value.name or ""
            row[field.attname if field.is_relation else field.name] = value
        rows.append(row)
    return rows


def export_data(request):
    """Download everything the user has added, as JSON."""
    user = request.user
    plants = Plant.objects.filter(created_user=user)
    data = {
        "exported_at": timezone.now(),
        "account": _rows([user], exclude={"password", "id", "role", "is_active"})[0],
        "plants": _rows(plants, exclude={"created_user"}),
        "care_tasks": _rows(CareTask.objects.filter(plant__in=plants)),
        "care_logs": _rows(CareLog.objects.filter(plant__in=plants)),
        "water_reminders": _rows(WaterReminder.objects.filter(plant__in=plants)),
        "health_cases": _rows(HealthCase.objects.filter(plant__in=plants)),
        "health_checks": _rows(HealthCheck.objects.filter(plant__in=plants)),
        "notifications": _rows(Notification.objects.filter(recipient=user), exclude={"recipient"}),
    }
    response = HttpResponse(
        json.dumps(data, cls=DjangoJSONEncoder, indent=2), content_type="application/json"
    )
    filename = f"plant-care-data-{timezone.localdate():%Y-%m-%d}.json"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_POST
def delete_account(request):
    user = request.user
    form = DeleteAccountForm(request.POST, user=user)
    if not form.is_valid():
        messages.error(request, form.errors["password"][0])
        return redirect(_settings_url("privacy"))

    # Uploaded photos are files on disk; the rows go with the account.
    files = [user.avatar] if user.avatar else []
    files += [p.image for p in Plant.objects.filter(created_user=user).exclude(image="")]
    files += [c.image for c in HealthCheck.objects.filter(plant__created_user=user).exclude(image="")]
    with transaction.atomic():
        user.delete()
        transaction.on_commit(lambda: [f.storage.delete(f.name) for f in files])
    auth_logout(request)
    messages.success(request, "Your account and all of its data were deleted.")
    return redirect("login")

