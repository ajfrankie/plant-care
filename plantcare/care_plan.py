"""Work out a plant's care schedule from its species' care needs.

The plan is a list of recurring tasks (watering, fertilizing, pruning), each
with an interval in days and a note explaining how it was worked out. Saving
the plan replaces the plant's open auto-generated tasks; tasks the user
scheduled by hand are never touched.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import CareTask
from .models.choices import Fertilizing, Humidity, Light, Watering

WATERING_DAYS = {
    Watering.DAILY: 1,
    Watering.EVERY_2_3_DAYS: 3,
    Watering.WEEKLY: 7,
    Watering.BIWEEKLY: 14,
    Watering.MONTHLY: 30,
    Watering.RARELY: 45,
}

FERTILIZING_DAYS = {
    Fertilizing.WEEKLY: 7,
    Fertilizing.BIWEEKLY: 14,
    Fertilizing.MONTHLY: 30,
    Fertilizing.QUARTERLY: 90,
    Fertilizing.SEASONALLY: 90,
}

# Faster growers need feeding and trimming more often.
GROWTH_FERTILIZING_DAYS = {"fast": 30, "moderate": 60, "slow": 90}
GROWTH_PRUNING_DAYS = {"fast": 30, "moderate": 60, "slow": 120}
DEFAULT_PRUNING_DAYS = 60

# Bright sun and dry air dry the soil out sooner; shade and humid air slow it down.
LIGHT_FACTOR = {
    Light.FULL_SUN: (0.8, "full sun dries the soil faster"),
    Light.PARTIAL_SUN: (0.9, "sun dries the soil a little faster"),
    Light.LOW: (1.25, "low light keeps the soil moist longer"),
}
HUMIDITY_FACTOR = {
    Humidity.LOW: (0.9, "dry air"),
    Humidity.HIGH: (1.1, "humid air"),
    Humidity.VERY_HIGH: (1.2, "very humid air"),
}

# A newly planned plant is fed after it has had time to settle in.
FIRST_FEED_AFTER_DAYS = 14


@dataclass
class PlannedTask:
    kind: str
    every_days: int
    first_due: object  # date
    reason: str

    @property
    def label(self):
        return CareTask.Kind(self.kind).label


def _adjust(days, factors):
    """Apply (factor, reason) pairs to a watering interval of a week or more."""
    reasons = []
    if days >= 7:
        for factor, reason in factors:
            days *= factor
            reasons.append(reason)
    return max(1, round(days)), reasons


def analyse(plant, today=None):
    """Return the recommended recurring tasks for ``plant``."""
    today = today or timezone.localdate()
    species = plant.plant_species

    if species is None:
        # Nothing to analyse: water on the check interval the user chose.
        return [PlannedTask(
            CareTask.Kind.WATER, plant.check_interval_days, today,
            f"Every {plant.check_interval_days} days, from your check interval "
            "(link a species for a tailored plan)",
        )]

    plan = []

    # Watering: species frequency, adjusted for light and humidity.
    base = WATERING_DAYS.get(species.watering, plant.check_interval_days)
    factors = [f for f in (LIGHT_FACTOR.get(species.light), HUMIDITY_FACTOR.get(species.humidity)) if f]
    water_days, adjustments = _adjust(base, factors)
    reason = f"{species.get_watering_display()} watering for {species.common_name}"
    if adjustments:
        reason += f", adjusted for {' and '.join(adjustments)}"
    plan.append(PlannedTask(CareTask.Kind.WATER, water_days, today, reason))

    # Fertilizing: species frequency, or estimated from how fast it grows.
    if species.fertilizing in FERTILIZING_DAYS:
        feed_days = FERTILIZING_DAYS[species.fertilizing]
        reason = f"{species.get_fertilizing_display()} feeding for {species.common_name}"
    else:
        feed_days = GROWTH_FERTILIZING_DAYS.get(species.growth_rate, 60)
        reason = "Estimated from its growth rate" if species.growth_rate else "General feeding guideline"
    plan.append(PlannedTask(
        CareTask.Kind.FERTILIZE, feed_days,
        today + timedelta(days=min(feed_days, FIRST_FEED_AFTER_DAYS)), reason,
    ))

    # Pruning / maintenance: from growth rate.
    prune_days = GROWTH_PRUNING_DAYS.get(species.growth_rate, DEFAULT_PRUNING_DAYS)
    reason = (f"{species.get_growth_rate_display()} grower" if species.growth_rate
              else "General maintenance guideline")
    plan.append(PlannedTask(
        CareTask.Kind.PRUNE, prune_days, today + timedelta(days=prune_days), reason,
    ))

    return plan


@transaction.atomic
def apply(plant, today=None):
    """Replace the plant's open auto-generated tasks with a fresh plan."""
    plan = analyse(plant, today)
    plant.tasks.filter(auto_generated=True, completed_at__isnull=True).delete()
    CareTask.objects.bulk_create([
        CareTask(
            plant=plant, kind=item.kind, due_date=item.first_due,
            repeat_every_days=item.every_days, notes=item.reason[:200],
            auto_generated=True,
        )
        for item in plan
    ])
    return plan


def summary(plan):
    """e.g. "Watering every 7 days, Fertilizing every 30 days"."""
    return ", ".join(
        f"{item.label} every {item.every_days} day{'s' if item.every_days != 1 else ''}"
        for item in plan
    )
