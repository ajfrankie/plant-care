from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .species import PlantSpecies


class Plant(models.Model):
    """A plant in one user's personal collection."""

    class Status(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        ATTENTION = "attention", "Needs Attention"
        CRITICAL = "critical", "Critical"

    created_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plants"
    )
    plant_species = models.ForeignKey(
        PlantSpecies, on_delete=models.SET_NULL, null=True, blank=True, related_name="plants"
    )

    name = models.CharField(max_length=120)
    nickname = models.CharField(max_length=120, blank=True)
    planting_date = models.DateField()
    check_interval_days = models.PositiveSmallIntegerField(
        default=7, validators=[MinValueValidator(1), MaxValueValidator(365)]
    )
    status = models.CharField(max_length=20, choices=Status, default=Status.HEALTHY)
    image = models.ImageField(upload_to="plants/%Y/%m/", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def next_check_date(self):
        """Last care activity (or the day it was added) plus the check interval."""
        last_care = getattr(self, "last_care_at", None)
        if last_care is None and not hasattr(self, "last_care_at"):
            last_care = self.care_logs.aggregate(m=models.Max("performed_at"))["m"]
        start = last_care or self.created_at or timezone.now()
        return timezone.localdate(start) + timedelta(days=self.check_interval_days)

    @property
    def days_until_check(self):
        return (self.next_check_date - timezone.localdate()).days
