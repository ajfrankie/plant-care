"""Turn the user's care schedules into notifications.

``sync`` is idempotent: each reminder has a ``key`` naming its source and the day
it is about, so calling it on every page load creates each one only once.
Cleared notifications are kept (hidden) so they are not created again.
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import CareTask, HealthCase, Notification, WaterReminder

HEALTH_ALERT_DAYS = 7  # health cases opened this recently get an alert

# (title when due, title when overdue) for each task kind.
TASK_TITLES = {
    CareTask.Kind.WATER: ("{plant} needs watering", "{plant} – watering overdue"),
    CareTask.Kind.FERTILIZE: ("{plant} needs fertilizing", "{plant} – fertilizing overdue"),
    CareTask.Kind.PRUNE: ("Time to prune {plant}", "{plant} – pruning overdue"),
    CareTask.Kind.HEALTH: ("Photo update due for {plant}", "{plant} – photo update overdue"),
}


def _days(n):
    return f"{n} day{'s' if n != 1 else ''}"


def _due_state(due, today):
    """'overdue', 'today' or 'soon' (tomorrow)."""
    if due < today:
        return "overdue"
    return "today" if due == today else "soon"


def _task_notification(task, today):
    state = _due_state(task.due_date, today)
    plant = task.plant.name
    due_title, overdue_title = TASK_TITLES[task.kind]
    label = task.get_kind_display().lower()
    if state == "overdue":
        late = (today - task.due_date).days
        title = overdue_title.format(plant=plant)
        message = f"{task.get_kind_display()} for {plant} was due {task.due_date:%b} {task.due_date.day} ({_days(late)} ago)."
        kind = Notification.Kind.OVERDUE
    elif state == "today":
        title = due_title.format(plant=plant)
        message = f"{task.get_kind_display()} for {plant} is due today."
        kind = Notification.Kind.HEALTH if task.kind == CareTask.Kind.HEALTH else Notification.Kind.REMINDER
    else:
        title = f"Upcoming: {label} for {plant}"
        message = f"{task.get_kind_display()} for {plant} is due tomorrow."
        kind = Notification.Kind.HEALTH if task.kind == CareTask.Kind.HEALTH else Notification.Kind.REMINDER
    if task.notes:
        message += f" {task.notes}"
    return Notification(
        kind=kind, plant=task.plant, task=task, title=title[:160], message=message,
        key=f"task:{task.pk}:{state}",
    )


def _water_notification(reminder, today):
    state = _due_state(reminder.next_due_date, today)
    plant = reminder.plant.name
    how = reminder.get_method_display().lower()
    if reminder.amount_ml:
        how += f", {reminder.amount_ml} ml"
    if state == "overdue":
        late = (today - reminder.next_due_date).days
        title = f"{plant} – watering overdue"
        message = f"Watering for {plant} is {_days(late)} overdue ({how})."
        kind = Notification.Kind.OVERDUE
    elif state == "today":
        title = f"{plant} needs watering"
        message = f"{plant} is due for watering today at {reminder.reminder_time:%H:%M} ({how})."
        kind = Notification.Kind.REMINDER
    else:
        title = f"Upcoming: watering for {plant}"
        message = f"{plant} is due for watering tomorrow ({how})."
        kind = Notification.Kind.REMINDER
    if reminder.notes:
        message += f" {reminder.notes}"
    return Notification(
        kind=kind, plant=reminder.plant, water_reminder=reminder, title=title[:160], message=message,
        key=f"water:{reminder.pk}:{reminder.next_due_date.isoformat()}:{state}",
    )


def _health_notification(case):
    message = f"{case.get_severity_display()} issue found on {case.plant.name}."
    message += f" Add a photo update every {_days(case.check_every_days)} to track how it's going."
    return Notification(
        kind=Notification.Kind.HEALTH, plant=case.plant, health_case=case,
        title=f"Health issue on {case.plant.name}: {case.title}"[:160], message=message,
        key=f"case:{case.pk}:open",
    )


def sync(user):
    """Create any notifications the user's schedules call for. Returns how many were added."""
    today = timezone.localdate()
    soon = today + timedelta(days=1)
    candidates = []

    tasks = (
        CareTask.objects.filter(plant__created_user=user, completed_at__isnull=True, due_date__lte=soon)
        .select_related("plant")
    )
    watered_by_task = set()
    for task in tasks:
        candidates.append(_task_notification(task, today))
        if task.kind == CareTask.Kind.WATER:
            watered_by_task.add(task.plant_id)

    reminders = (
        WaterReminder.objects.filter(plant__created_user=user, is_active=True, next_due_date__lte=soon)
        .select_related("plant")
    )
    for reminder in reminders:
        # A watering task on the care schedule already covers this plant.
        if reminder.plant_id not in watered_by_task:
            candidates.append(_water_notification(reminder, today))

    recent_cases = (
        HealthCase.objects.filter(plant__created_user=user, started_at__gte=timezone.now() - timedelta(days=HEALTH_ALERT_DAYS))
        .exclude(status=HealthCase.Status.RESOLVED)
        .select_related("plant")
    )
    candidates.extend(_health_notification(case) for case in recent_cases)

    if not candidates:
        return 0
    existing = set(
        Notification.objects.filter(recipient=user, key__in=[n.key for n in candidates])
        .values_list("key", flat=True)
    )
    new = [n for n in candidates if n.key not in existing]
    for notification in new:
        notification.recipient = user
        # A newer reminder about the same thing replaces the older unread ones
        # (e.g. "due tomorrow" once it becomes "due today").
        source = {"task": notification.task} if notification.task else (
            {"water_reminder": notification.water_reminder} if notification.water_reminder else None
        )
        if source:
            Notification.objects.filter(
                recipient=user, is_read=False, is_dismissed=False, **source
            ).exclude(kind=Notification.Kind.COMPLETED).delete()
    try:
        with transaction.atomic():
            Notification.objects.bulk_create(new)
    except IntegrityError:
        # Another request created some of them at the same moment; add the rest one by one.
        for notification in new:
            try:
                with transaction.atomic():
                    notification.pk = None
                    notification.save()
            except IntegrityError:
                pass
    return len(new)


def _settle(**source):
    """Reminders about something now done no longer need attention."""
    Notification.objects.filter(is_read=False, **source).exclude(
        kind=Notification.Kind.COMPLETED
    ).update(is_read=True)


def task_completed(task, next_task=None):
    """Record a completed care task (already read: the user did it themselves)."""
    _settle(task=task)
    message = f"You completed {task.get_kind_display().lower()} for {task.plant.name}."
    if next_task:
        message += f" Next one is due {next_task.due_date:%b} {next_task.due_date.day}."
    Notification.objects.create(
        recipient=task.plant.created_user, plant=task.plant, kind=Notification.Kind.COMPLETED,
        title="Care task completed", message=message, is_read=True,
    )


def plant_watered(reminder):
    """Record a watering from a water reminder."""
    _settle(water_reminder=reminder)
    # Watering tasks it ticked off on the care schedule.
    _settle(task__plant=reminder.plant, task__kind=CareTask.Kind.WATER, task__completed_at__isnull=False)
    due = reminder.next_due_date
    Notification.objects.create(
        recipient=reminder.plant.created_user, plant=reminder.plant, kind=Notification.Kind.COMPLETED,
        title="Plant watered",
        message=f"You watered {reminder.plant.name}. Next watering is due {due:%b} {due.day}.",
        is_read=True,
    )
