from datetime import time, timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from .care import CareLog, CareTask
from .plant import Plant


class WaterReminder(models.Model):
    """A recurring reminder to water one plant (Watering Reminders page)."""

    class Method(models.TextChoices):
        TOP = "top", "Top watering"
        BOTTOM = "bottom", "Bottom watering"
        MIST = "mist", "Misting"
        SOAK = "soak", "Soak & drain"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="water_reminders")
    frequency_days = models.PositiveSmallIntegerField(
        default=7, validators=[MinValueValidator(1), MaxValueValidator(365)]
    )
    next_due_date = models.DateField()
    reminder_time = models.TimeField(default=time(9, 0))
    method = models.CharField(max_length=20, choices=Method, default=Method.TOP)
    amount_ml = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(20000)]
    )
    notes = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    last_watered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_due_date", "plant__name"]

    def __str__(self):
        return f"Water {self.plant} every {self.frequency_days} days"

    @property
    def days_until_due(self):
        return (self.next_due_date - timezone.localdate()).days

    @transaction.atomic
    def mark_watered(self):
        """Record a watering, push the next due date out, and tick off
        any watering task for this plant that is due on the care schedule."""
        now = timezone.now()
        today = timezone.localdate(now)
        self.last_watered_at = now
        self.next_due_date = today + timedelta(days=self.frequency_days)
        self.save(update_fields=["last_watered_at", "next_due_date", "updated_at"])

        details = [self.get_method_display()]
        if self.amount_ml:
            details.append(f"{self.amount_ml} ml")
        if self.notes:
            details.append(self.notes)
        CareLog.objects.create(
            plant=self.plant, activity=CareLog.Activity.WATERING,
            performed_at=now, notes=" · ".join(details),
        )

        due_tasks = self.plant.tasks.filter(
            kind=CareTask.Kind.WATER, completed_at__isnull=True, due_date__lte=today
        )
        for task in due_tasks:
            task.complete(log=False)  # already logged above

        from .. import notify
        notify.plant_watered(self)
