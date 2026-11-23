from django.db import models


class PlantIssue(models.Model):
    """A pest, disease or care problem in the Diseases & Pests library (managed by admins).

    Health cases point at one through ``HealthCase.issue_key`` (= ``key``), and the
    photo analysis is told every key so it can match what it sees.
    """

    class Type(models.TextChoices):
        PEST = "Pest", "Pest"
        FUNGAL = "Fungal disease", "Fungal disease"
        BACTERIAL = "Bacterial disease", "Bacterial disease"
        VIRAL = "Viral disease", "Viral disease"
        CARE = "Care problem", "Care problem"

    key = models.SlugField(max_length=40, unique=True)  # never changes once health cases use it
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=30, choices=Type)
    symptoms = models.TextField()
    # Steps of the organic cure, in order: [{"name", "step", "when", "how"}, ...]
    treatments = models.JSONField(default=list, blank=True)
    prevention = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def as_dict(self):
        """The shape the rest of the app uses (see ``health_library``)."""
        return {
            "name": self.name, "type": self.type, "symptoms": self.symptoms,
            "treatments": list(self.treatments), "prevention": self.prevention,
        }
