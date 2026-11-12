from django.urls import path

from .controllers import accounts, care, dashboard, library, plants, public, species

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
    path("watering-schedule/", care.watering, name="watering_schedule"),
    path("care-history/", care.history, name="care_history"),
]
