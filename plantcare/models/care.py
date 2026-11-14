from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .plant import Plant


class CareTask(models.Model):
    """Something scheduled to be done to a plant (care and watering schedules)."""

    class Kind(models.TextChoices):
        WATER = "water", "Watering"
        FERTILIZE = "fertilize", "Fertilizing"
        PRUNE = "prune", "Pruning/Maintenance"
        HEALTH = "health", "Health Check"

    # The care-history activity recorded when a task of each kind is completed.
    LOG_ACTIVITY = {
        Kind.WATER: "watering",
        Kind.FERTILIZE: "fertilizing",
        Kind.PRUNE: "maintenance",
        Kind.HEALTH: "health",
    }

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="tasks")
    kind = models.CharField(max_length=20, choices=Kind)
    due_date = models.DateField()
    # When set, completing the task schedules the next one this many days later.
    repeat_every_days = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(365)]
    )
    notes = models.CharField(max_length=200, blank=True)
    # Created by the care-plan analysis (replaced when the plan is regenerated).
    auto_generated = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.plant} on {self.due_date}"

    @property
    def is_done(self):
        return self.completed_at is not None

    def complete(self, log=True):
        """Mark done, log it in the care history, and schedule the next repeat.

        ``log=False`` skips the care-history entry (and reminder sync) when the
        caller has already recorded the activity, e.g. a water reminder.

        Returns the newly scheduled task, or None when the task doesn't repeat.
        """
        now = timezone.now()
        self.completed_at = now
        self.save(update_fields=["completed_at"])
        if log:
            CareLog.objects.create(
                plant=self.plant,
                activity=self.LOG_ACTIVITY[self.kind],
                performed_at=now,
                notes=self.notes,
            )
            if self.kind == self.Kind.WATER:
                # Watered from the schedule: the plant's due water reminders move on too.
                from .watering import WaterReminder
                today = timezone.localdate(now)
                for reminder in WaterReminder.objects.filter(
                    plant=self.plant, is_active=True, next_due_date__lte=today
                ):
                    reminder.last_watered_at = now
                    reminder.next_due_date = today + timedelta(days=reminder.frequency_days)
                    reminder.save(update_fields=["last_watered_at", "next_due_date", "updated_at"])
        if not self.repeat_every_days:
            return None
        return CareTask.objects.create(
            plant=self.plant,
            kind=self.kind,
            due_date=timezone.localdate(now) + timedelta(days=self.repeat_every_days),
            repeat_every_days=self.repeat_every_days,
            notes=self.notes,
            auto_generated=self.auto_generated,
        )


class CareLog(models.Model):
    """Something that was done to a plant (care history timeline)."""

    class Activity(models.TextChoices):
        WATERING = "watering", "Watering"
        FERTILIZING = "fertilizing", "Fertilizing"
        MAINTENANCE = "maintenance", "Pruning/Maintenance"
        HEALTH = "health", "Health Update"
        NOTE = "note", "Note"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="care_logs")
    activity = models.CharField(max_length=20, choices=Activity)
    performed_at = models.DateTimeField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-performed_at"]

    def __str__(self):
        return f"{self.get_activity_display()} {self.plant}"
