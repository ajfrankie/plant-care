"""Reshape the plant table to: id, created_user, plant_species, name, nickname,
planting_date, check_interval_days, status, created_at, updated_at."""
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plantcare", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField("plant", "owner", "created_user"),
        migrations.RenameField("plant", "species", "plant_species"),
        migrations.RenameField("plant", "health", "status"),
        migrations.AlterField(
            model_name="plant",
            name="created_user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="plants",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="plant",
            name="plant_species",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="plants",
                to="plantcare.plantspecies",
            ),
        ),
        migrations.AlterField(
            model_name="plant",
            name="status",
            field=models.CharField(
                choices=[
                    ("healthy", "Healthy"),
                    ("attention", "Needs Attention"),
                    ("critical", "Critical"),
                ],
                default="healthy",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="plant",
            name="nickname",
            field=models.CharField(blank=True, default="", max_length=120),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="plant",
            name="planting_date",
            field=models.DateField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="plant",
            name="check_interval_days",
            field=models.PositiveSmallIntegerField(
                default=7,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(365),
                ],
            ),
        ),
        migrations.RemoveField("plant", "scientific_name"),
        migrations.RemoveField("plant", "common_name"),
        migrations.RemoveField("plant", "location"),
        migrations.RemoveField("plant", "date_acquired"),
        migrations.RemoveField("plant", "notes"),
        migrations.RemoveField("plant", "watering"),
        migrations.RemoveField("plant", "next_watering_date"),
        migrations.RemoveField("plant", "light"),
        migrations.RemoveField("plant", "fertilizing"),
        migrations.RemoveField("plant", "temperature_range"),
        migrations.RemoveField("plant", "humidity"),
        migrations.RemoveField("plant", "photo"),
    ]
