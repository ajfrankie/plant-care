from django.db import models

from .choices import Fertilizing, Humidity, Light, SpecialFeature, Watering


class PlantSpecies(models.Model):
    """An entry in the shared Plant Library."""

    class Category(models.TextChoices):
        INDOOR = "indoor", "Indoor Plants"
        OUTDOOR = "outdoor", "Outdoor Plants"
        SUCCULENT = "succulent", "Succulents"
        FLOWERING = "flowering", "Flowering Plants"
        FOLIAGE = "foliage", "Foliage Plants"
        TROPICAL = "tropical", "Tropical Plants"
        DESERT = "desert", "Desert Plants"
        AIR_PURIFYING = "air_purifying", "Air Purifying"

    class Difficulty(models.TextChoices):
        VERY_EASY = "very_easy", "Very Easy"
        EASY = "easy", "Easy"
        MODERATE = "moderate", "Moderate"
        DIFFICULT = "difficult", "Difficult"
        EXPERT = "expert", "Expert"

    class GrowthRate(models.TextChoices):
        SLOW = "slow", "Slow"
        MODERATE = "moderate", "Moderate"
        FAST = "fast", "Fast"

    common_name = models.CharField(max_length=120)
    scientific_name = models.CharField(max_length=160, unique=True)
    family = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=20, choices=Category)
    origin = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    difficulty = models.CharField(max_length=20, choices=Difficulty)

    light = models.CharField(max_length=20, choices=Light)
    watering = models.CharField(max_length=20, choices=Watering)
    fertilizing = models.CharField(max_length=20, choices=Fertilizing, blank=True)
    temperature_range = models.CharField(max_length=40, blank=True)
    humidity = models.CharField(max_length=20, choices=Humidity, blank=True)
    soil_type = models.JSONField(default=list, blank=True)  # list of strings

    growth_rate = models.CharField(max_length=20, choices=GrowthRate, blank=True)
    mature_height = models.CharField(max_length=40, blank=True)
    mature_width = models.CharField(max_length=40, blank=True)
    foliage_color = models.CharField(max_length=60, blank=True)
    flower_color = models.JSONField(default=list, blank=True)  # list of strings
    special_features = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["common_name"]
        verbose_name_plural = "plant species"

    def __str__(self):
        return f"{self.common_name} ({self.scientific_name})"

    @property
    def special_feature_labels(self):
        """Display names for the comma-separated special_features."""
        labels = dict(SpecialFeature.choices)
        return [labels[f] for f in self.special_features.split(",") if f in labels]
