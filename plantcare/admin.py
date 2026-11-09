from django.contrib import admin

from .models import CareLog, CareTask, Notification, Plant, PlantSpecies


@admin.register(PlantSpecies)
class PlantSpeciesAdmin(admin.ModelAdmin):
    list_display = ("common_name", "scientific_name", "category", "difficulty")
    list_filter = ("category", "difficulty")
    search_fields = ("common_name", "scientific_name")


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "location", "health", "next_watering_date")
    list_filter = ("health", "location")
    search_fields = ("name", "scientific_name")


@admin.register(CareTask)
class CareTaskAdmin(admin.ModelAdmin):
    list_display = ("plant", "kind", "due_date", "completed_at")
    list_filter = ("kind",)


@admin.register(CareLog)
class CareLogAdmin(admin.ModelAdmin):
    list_display = ("plant", "activity", "performed_at")
    list_filter = ("activity",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")
