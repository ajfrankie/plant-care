"""Store PlantSpecies.soil_type and flower_color as JSON lists of strings.

Existing text is split on commas, e.g. "White, Pink" -> ["White", "Pink"].
"""
import json

from django.db import migrations, models

FIELDS = ("soil_type", "flower_color")


def text_to_json(apps, schema_editor):
    PlantSpecies = apps.get_model("plantcare", "PlantSpecies")
    for species in PlantSpecies.objects.only("pk", *FIELDS):
        values = {
            field: json.dumps([
                part.strip() for part in (getattr(species, field) or "").split(",") if part.strip()
            ])
            for field in FIELDS
        }
        PlantSpecies.objects.filter(pk=species.pk).update(**values)


def json_to_text(apps, schema_editor):
    PlantSpecies = apps.get_model("plantcare", "PlantSpecies")
    for species in PlantSpecies.objects.only("pk", *FIELDS):
        values = {}
        for field in FIELDS:
            try:
                items = json.loads(getattr(species, field) or "[]")
            except ValueError:
                items = []
            values[field] = ", ".join(str(item) for item in items)
        PlantSpecies.objects.filter(pk=species.pk).update(**values)


class Migration(migrations.Migration):

    dependencies = [
        ("plantcare", "0004_remove_species_photo"),
    ]

    operations = [
        # Widen to text first so the JSON strings fit, then convert the type.
        migrations.AlterField("plantspecies", "soil_type", models.TextField(blank=True)),
        migrations.AlterField("plantspecies", "flower_color", models.TextField(blank=True)),
        migrations.RunPython(text_to_json, json_to_text),
        migrations.AlterField(
            "plantspecies", "soil_type", models.JSONField(blank=True, default=list)
        ),
        migrations.AlterField(
            "plantspecies", "flower_color", models.JSONField(blank=True, default=list)
        ),
    ]
