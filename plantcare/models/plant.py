from django.conf import settings
from django.db import models

from .choices import Fertilizing, Humidity, Light, Watering
from .species import PlantSpecies


class Plant(models.Model):
    """A plant in one user's personal collection."""

    class Location(models.TextChoices):
        LIVING_ROOM = "living_room", "Living Room"
        BEDROOM = "bedroom", "Bedroom"
        KITCHEN = "kitchen", "Kitchen"
        BATHROOM = "bathroom", "Bathroom"
        BALCONY = "balcony", "Balcony"
        GARDEN = "garden", "Garden"
        OFFICE = "office", "Office"
        OTHER = "other", "Other"

    class Health(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        ATTENTION = "attention", "Needs Attention"
        CRITICAL = "critical", "Critical"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plants"
    )
    species = models.ForeignKey(
        PlantSpecies, on_delete=models.SET_NULL, null=True, blank=True, related_name="plants"
    )

    name = models.CharField(max_length=120)
    scientific_name = models.CharField(max_length=160, blank=True)
    common_name = models.CharField(max_length=120, blank=True)
    location = models.CharField(max_length=20, choices=Location)
    date_acquired = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    watering = models.CharField(max_length=20, choices=Watering)
    next_watering_date = models.DateField(null=True, blank=True)
    light = models.CharField(max_length=20, choices=Light, blank=True)
    fertilizing = models.CharField(max_length=20, choices=Fertilizing, blank=True)
    temperature_range = models.CharField(max_length=40, blank=True)
    humidity = models.CharField(max_length=20, choices=Humidity, blank=True)

    photo = models.ImageField(upload_to="plants/", blank=True)
    health = models.CharField(max_length=20, choices=Health, default=Health.HEALTHY)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
