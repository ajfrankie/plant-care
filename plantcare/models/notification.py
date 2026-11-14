from django.conf import settings
from django.db import models
from django.urls import reverse

from .care import CareTask
from .health import HealthCase
from .plant import Plant
from .watering import WaterReminder


class Notification(models.Model):
    """Something the user should know about (Notifications page and header bell).

    Reminders, overdue alerts and health alerts are created by ``plantcare.notify.sync``
    from the user's schedules; ``key`` stops the same one being created twice.
    """

    class Kind(models.TextChoices):
        REMINDER = "reminder", "Reminder"
        OVERDUE = "overdue", "Overdue"
        HEALTH = "health", "Health Alert"
        COMPLETED = "completed", "Completed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    plant = models.ForeignKey(
        Plant, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    # What the notification is about, so it can be acted on from the page.
    task = models.ForeignKey(
        CareTask, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    water_reminder = models.ForeignKey(
        WaterReminder, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    health_case = models.ForeignKey(
        HealthCase, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    kind = models.CharField(max_length=20, choices=Kind, default=Kind.REMINDER)
    title = models.CharField(max_length=160)
    message = models.TextField(blank=True)
    key = models.CharField(max_length=80, null=True, blank=True)  # NULL = no de-duplication
    is_read = models.BooleanField(default=False)
    # Cleared by the user: hidden, but kept so it isn't created again.
    is_dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["recipient", "key"], name="unique_notification_key_per_user"),
        ]

    def __str__(self):
        return self.title

    @property
    def age(self):
        """"Just now", or e.g. "15 minutes ago"."""
        from django.utils import timezone
        from django.utils.timesince import timesince
        if (timezone.now() - self.created_at).total_seconds() < 60:
            return "Just now"
        return f"{timesince(self.created_at)} ago"

    @property
    def target_url(self):
        """Where opening the notification takes the user."""
        if self.health_case_id:
            return reverse("health_case", args=[self.health_case_id])
        if self.water_reminder_id:
            return reverse("watering_schedule")
        if self.plant_id:
            return reverse("plant_view", args=[self.plant_id])
        return reverse("notifications")

    @property
    def can_complete(self):
        """Whether "Mark Complete" still has something to do."""
        if self.task_id:
            return self.task.completed_at is None
        if self.water_reminder_id:
            from django.utils import timezone
            reminder = self.water_reminder
            return reminder.is_active and reminder.next_due_date <= timezone.localdate()
        return False
