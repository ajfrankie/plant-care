from django.db import models


class ContactMessage(models.Model):
    """A message sent from the About page's contact form."""

    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=160, blank=True)
    message = models.TextField(max_length=3000)
    is_handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.subject or self.message[:40]}"
