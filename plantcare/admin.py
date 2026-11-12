from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CareLog, CareTask, Notification, Plant, PlantSpecies, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "full_name", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("email", "full_name")
    ordering = ("-created_at",)
    filter_horizontal = ()
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Profile", {"fields": ("full_name",)}),
        ("Access", {"fields": ("role", "is_active")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "full_name", "role", "is_active",
                "usable_password", "password1", "password2",
            ),
        }),
    )


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
