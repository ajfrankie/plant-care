from django.urls import path

from .controllers import accounts, care, dashboard, health, library, plants, public, species, watering

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
    path("plant-health/", health.index, name="plant_health"),
    path("plant-health/check/", health.new_check, name="health_check_new"),
    path("plant-health/<int:pk>/", health.case_detail, name="health_case"),
    path("plant-health/<int:pk>/update/", health.case_update, name="health_case_update"),
    path("plant-health/<int:pk>/issue/", health.case_set_issue, name="health_case_issue"),
    path("plant-health/<int:pk>/reanalyse/", health.case_reanalyse, name="health_case_reanalyse"),
    path("plant-health/<int:pk>/resolve/", health.case_resolve, name="health_case_resolve"),
    path("plant-health/<int:pk>/frequency/", health.case_frequency, name="health_case_frequency"),
    path("plant-health/<int:pk>/delete/", health.case_delete, name="health_case_delete"),

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
