from django.urls import path

from .controllers import accounts, care, dashboard, library, plants, public, species, watering

urlpatterns = [
    # Public site
    path("", public.home, name="home"),
    path("explore/", public.explore, name="explore"),
    path("care-guides/", public.care_guides, name="care_guides"),
    path("about/", public.about, name="about"),
    path("style-guide/", public.style_guide, name="style_guide"),

    # Accounts
    path("login/", accounts.login, name="login"),
    path("logout/", accounts.logout, name="logout"),
    path("register/", accounts.register, name="register"),
    path("settings/", accounts.settings, name="settings"),
    path("notifications/", accounts.notifications, name="notifications"),

    # App
    path("dashboard/", dashboard.index, name="dashboard"),

    path("my-plants/", plants.index, name="my_plants"),
    path("my-plants/add/", plants.add, name="plant_add"),
    path("my-plants/<int:pk>/", plants.view, name="plant_view"),
    path("my-plants/<int:pk>/edit/", plants.edit, name="plant_edit"),
    path("my-plants/<int:pk>/care-plan/", plants.replan, name="plant_replan"),
    path("my-plants/details/", plants.details, name="plant_details"),
    path("plant-health/", plants.health, name="plant_health"),

    path("library/", library.index, name="library"),
    path("library/create/", library.create, name="library_create"),
    path("library/view/", library.view, name="library_view"),
    path("library/edit/", library.edit, name="library_edit"),

    path("species/", species.index, name="species"),
    path("species/add/", species.add, name="species_add"),
    path("species/<int:pk>/edit/", species.edit, name="species_edit"),

    path("care-schedule/", care.schedule, name="care_schedule"),
    path("care-schedule/auto-plan/", care.auto_plan, name="care_auto_plan"),
    path("care-schedule/tasks/add/", care.task_add, name="care_task_add"),
    path("care-schedule/tasks/<int:pk>/complete/", care.task_complete, name="care_task_complete"),
    path("care-schedule/tasks/<int:pk>/delete/", care.task_delete, name="care_task_delete"),
    path("watering-schedule/", watering.index, name="watering_schedule"),
    path("watering-schedule/add/", watering.add, name="water_reminder_add"),
    path("watering-schedule/auto/", watering.auto_create, name="water_reminder_auto"),
    path("watering-schedule/water-all/", watering.water_all, name="water_reminder_water_all"),
    path("watering-schedule/<int:pk>/edit/", watering.edit, name="water_reminder_edit"),
    path("watering-schedule/<int:pk>/water/", watering.water, name="water_reminder_water"),
    path("watering-schedule/<int:pk>/toggle/", watering.toggle, name="water_reminder_toggle"),
    path("watering-schedule/<int:pk>/delete/", watering.delete, name="water_reminder_delete"),
    path("care-history/", care.history, name="care_history"),
]
