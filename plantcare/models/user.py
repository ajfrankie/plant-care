import uuid
from datetime import time

from django.conf import settings

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from .watering import WaterReminder


class UserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(
            email=self.normalize_email(email).lower(),
            full_name=full_name,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        extra_fields.update(role=User.Role.ADMIN, is_active=True)
        return self.create_user(email, full_name, password, **extra_fields)


class User(AbstractBaseUser):
    """An account that signs in with its email address."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(
        unique=True,
        error_messages={"unique": "An account with this email already exists."},
    )
    role = models.CharField(
        max_length=20, choices=Role, default=Role.USER, db_default=Role.USER
    )
    is_active = models.BooleanField(default=False, db_default=False)

    # Settings page: profile photo and preferences.
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", blank=True)
    timezone = models.CharField(max_length=64, default=settings.TIME_ZONE)
    notify_care_tasks = models.BooleanField(
        "Fertilizing and pruning reminders", default=True
    )
    notify_watering = models.BooleanField("Watering reminders", default=True)
    notify_health = models.BooleanField("Plant health alerts", default=True)
    default_reminder_time = models.TimeField(default=time(9, 0))
    default_watering_method = models.CharField(
        max_length=20, choices=WaterReminder.Method, default=WaterReminder.Method.TOP
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    last_login = None  # not part of this table

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def first_name(self):
        return self.full_name.split()[0] if self.full_name.strip() else ""

    @property
    def initials(self):
        parts = self.full_name.split()
        if not parts:
            return self.email[:1].upper()
        return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

    # Django admin access is driven by role, not separate staff/superuser flags.
    @property
    def is_staff(self):
        return self.role == self.Role.ADMIN

    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_staff

    def has_module_perms(self, app_label):
        return self.is_active and self.is_staff
