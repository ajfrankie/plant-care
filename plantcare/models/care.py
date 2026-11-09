from django.db import models

from .plant import Plant


class CareTask(models.Model):
    """Something scheduled to be done to a plant (care and watering schedules)."""

    class Kind(models.TextChoices):
        WATER = "water", "Watering"
        FERTILIZE = "fertilize", "Fertilizing"
        PRUNE = "prune", "Pruning/Maintenance"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="tasks")
    kind = models.CharField(max_length=20, choices=Kind)
    due_date = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.plant} on {self.due_date}"


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
