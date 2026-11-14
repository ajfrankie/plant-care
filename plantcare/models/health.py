from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from .care import CareLog, CareTask
from .plant import Plant


class HealthCase(models.Model):
    """A health problem on one plant, tracked with regular photo updates."""

    class Severity(models.TextChoices):
        MILD = "mild", "Mild"
        MODERATE = "moderate", "Moderate"
        SEVERE = "severe", "Severe"

    class Status(models.TextChoices):
        ACTIVE = "active", "Being treated"
        IMPROVING = "improving", "Improving"
        RESOLVED = "resolved", "Resolved"

    class Source(models.TextChoices):
        USER = "user", "Entered by you"
        AI = "ai", "Found from photo"
        UNKNOWN = "unknown", "Not identified yet"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="health_cases")
    title = models.CharField(max_length=120)
    issue_key = models.CharField(max_length=40, blank=True)  # key in health_library.ISSUES
    severity = models.CharField(max_length=20, choices=Severity, default=Severity.MODERATE)
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
    source = models.CharField(max_length=20, choices=Source, default=Source.USER)
    check_every_days = models.PositiveSmallIntegerField(
        default=7, validators=[MinValueValidator(1), MaxValueValidator(60)]
    )
    next_check_date = models.DateField()
    started_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.title} on {self.plant}"

    @property
    def is_open(self):
        return self.status != self.Status.RESOLVED

    @property
    def latest_check(self):
        return self.checks.order_by("-created_at").first()

    @property
    def library_entry(self):
        from ..health_library import get
        return get(self.issue_key)

    # Photo-update reminders show on the Care Schedule as "Health Check" tasks.

    def _clear_reminders(self):
        self.plant.tasks.filter(
            kind=CareTask.Kind.HEALTH, auto_generated=True, completed_at__isnull=True
        ).delete()

    def schedule_next_check(self, from_date=None):
        """Set the next photo update and its reminder on the care schedule."""
        start = from_date or timezone.localdate()
        self.next_check_date = start + timedelta(days=self.check_every_days)
        self.save(update_fields=["next_check_date"])
        self._clear_reminders()
        CareTask.objects.create(
            plant=self.plant, kind=CareTask.Kind.HEALTH, due_date=self.next_check_date,
            repeat_every_days=self.check_every_days, auto_generated=True,
            notes=f"Photo update: {self.title}"[:200],
        )

    @transaction.atomic
    def resolve(self):
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolved_at"])
        if not self.plant.health_cases.exclude(status=self.Status.RESOLVED).exists():
            self._clear_reminders()
        CareLog.objects.create(
            plant=self.plant, activity=CareLog.Activity.HEALTH,
            performed_at=self.resolved_at, notes=f"Resolved: {self.title}",
        )
        sync_plant_status(self.plant)

    @transaction.atomic
    def reopen(self):
        self.status = self.Status.ACTIVE
        self.resolved_at = None
        self.save(update_fields=["status", "resolved_at"])
        self.schedule_next_check()
        sync_plant_status(self.plant)


class HealthCheck(models.Model):
    """One photo of a plant (or a leaf) and what was found in it."""

    class Progress(models.TextChoices):
        FIRST = "first", "First photo"
        BETTER = "better", "Getting better"
        SAME = "same", "About the same"
        WORSE = "worse", "Getting worse"

    class Analysis(models.TextChoices):
        SKIPPED = "skipped", "Not analysed"
        DONE = "done", "Analysed"
        FAILED = "failed", "Analysis failed"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="health_checks")
    case = models.ForeignKey(
        HealthCase, on_delete=models.CASCADE, null=True, blank=True, related_name="checks"
    )
    image = models.ImageField(upload_to="health/%Y/%m/")
    notes = models.TextField(blank=True)  # symptoms / what the user noticed
    progress = models.CharField(max_length=20, choices=Progress, default=Progress.FIRST)
    analysis_status = models.CharField(max_length=20, choices=Analysis, default=Analysis.SKIPPED)
    analysis = models.JSONField(default=dict, blank=True)  # result of the photo analysis
    analysis_error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Health photo of {self.plant} ({self.created_at:%Y-%m-%d})"


def sync_plant_status(plant):
    """Plant status follows its worst open health case."""
    open_cases = plant.health_cases.exclude(status=HealthCase.Status.RESOLVED)
    if open_cases.filter(severity=HealthCase.Severity.SEVERE).exists():
        status = Plant.Status.CRITICAL
    elif open_cases.exists():
        status = Plant.Status.ATTENTION
    else:
        status = Plant.Status.HEALTHY
    if plant.status != status:
        plant.status = status
        plant.save(update_fields=["status", "updated_at"])
