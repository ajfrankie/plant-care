from django.conf import settings
from django.db import models

from .plant import Plant


class Notification(models.Model):
    class Kind(models.TextChoices):
        REMINDER = "reminder", "Reminder"
        OVERDUE = "overdue", "Overdue"
        COMPLETED = "completed", "Completed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    plant = models.ForeignKey(
        Plant, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    kind = models.CharField(max_length=20, choices=Kind, default=Kind.REMINDER)
    title = models.CharField(max_length=160)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
