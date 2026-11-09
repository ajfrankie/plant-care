"""Option lists shared by the plant and species forms."""
from django.db import models


class Light(models.TextChoices):
    FULL_SUN = "full_sun", "Full Sun"
    PARTIAL_SUN = "partial_sun", "Partial Sun"
    BRIGHT_INDIRECT = "bright_indirect", "Bright Indirect"
    MEDIUM = "medium", "Medium Light"
    LOW = "low", "Low Light"
    LOW_TO_BRIGHT = "low_to_bright", "Low to Bright"


class Watering(models.TextChoices):
    DAILY = "daily", "Daily"
    EVERY_2_3_DAYS = "every_2_3_days", "Every 2-3 days"
    WEEKLY = "weekly", "Weekly"
    BIWEEKLY = "biweekly", "Bi-weekly"
    MONTHLY = "monthly", "Monthly"
    RARELY = "rarely", "Rarely"


class Fertilizing(models.TextChoices):
    WEEKLY = "weekly", "Weekly"
    BIWEEKLY = "biweekly", "Bi-weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    SEASONALLY = "seasonally", "Seasonally"


class Humidity(models.TextChoices):
    LOW = "low", "Low (30-40%)"
    MEDIUM = "medium", "Medium (40-60%)"
    HIGH = "high", "High (60-80%)"
    VERY_HIGH = "very_high", "Very High (80%+)"
