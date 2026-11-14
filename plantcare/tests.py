import uuid
from datetime import date, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import LoginForm
from .models import (
    CareLog, CareTask, HealthCase, HealthCheck, Plant, PlantSpecies, User, WaterReminder,
)
from .urls import urlpatterns


class RegisterTests(TestCase):
    valid_data = {
        "full_name": "Jane Doe",
        "email": "Jane@Example.com",
        "password": "mossy-Fern-42!",
        "confirm_password": "mossy-Fern-42!",
        "terms": "on",
    }

    def post(self, **overrides):
        return self.client.post(reverse("register"), {**self.valid_data, **overrides})

    def assertRejected(self, response, field):
        self.assertEqual(response.status_code, 200)
        self.assertIn(field, response.context["form"].errors)

    def test_page_posts_every_form_field(self):
        html = self.client.get(reverse("register")).content.decode()
        self.assertIn('<form method="post"', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        for name in self.valid_data:
            with self.subTest(name=name):
                self.assertIn(f'name="{name}"', html)

    def test_valid_registration_creates_user_with_defaults(self):
        before = User.objects.count()
        response = self.post()
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(User.objects.count(), before + 1)

        user = User.objects.get(email="jane@example.com")
        self.assertIsInstance(user.id, uuid.UUID)
        self.assertEqual(user.full_name, "Jane Doe")
        self.assertEqual(user.role, User.Role.USER)
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.created_at)
        self.assertIsNotNone(user.updated_at)

    def test_password_is_hashed(self):
        self.post()
        user = User.objects.get(email="jane@example.com")
        self.assertNotEqual(user.password, self.valid_data["password"])
        self.assertTrue(user.check_password(self.valid_data["password"]))

    def test_success_message_shown_on_login_page(self):
        response = self.client.post(reverse("register"), self.valid_data, follow=True)
        self.assertContains(response, "Your account has been created.")

    def test_post_cannot_set_role_or_activate(self):
        self.post(role="admin", is_active="1")
        user = User.objects.get(email="jane@example.com")
        self.assertEqual(user.role, User.Role.USER)
        self.assertFalse(user.is_active)

    def test_duplicate_email_rejected_regardless_of_case(self):
        self.post()
        self.assertRejected(self.post(email="JANE@example.com"), "email")
        self.assertEqual(User.objects.filter(email__iexact="jane@example.com").count(), 1)

    def test_invalid_submissions_rejected(self):
        cases = [
            ("full_name", {"full_name": "   "}),
            ("email", {"email": "not-an-email"}),
            ("confirm_password", {"confirm_password": "something-Else-9"}),
            ("password", {"password": "12345678", "confirm_password": "12345678"}),
            ("password", {"password": "jane@example.com", "confirm_password": "jane@example.com"}),
            ("terms", {"terms": ""}),
        ]
        for field, overrides in cases:
            with self.subTest(field=field, overrides=overrides):
                self.assertRejected(self.post(**overrides), field)
                self.assertFalse(User.objects.exists())

    def test_errors_keep_entered_values_but_not_passwords(self):
        html = self.post(confirm_password="nope").content.decode()
        self.assertIn('value="Jane Doe"', html)
        self.assertNotIn(self.valid_data["password"], html)

    def test_post_without_csrf_token_rejected(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("register"), self.valid_data)
        self.assertEqual(response.status_code, 403)

    def test_inactive_user_cannot_authenticate(self):
        self.post()
        self.assertFalse(
            self.client.login(email="jane@example.com", password=self.valid_data["password"])
        )


class LoginTests(TestCase):
    password = "mossy-Fern-42!"

    def setUp(self):
        self.active = User.objects.create_user(
            "active@example.com", "Active", self.password, is_active=True
        )
        self.inactive = User.objects.create_user("waiting@example.com", "Waiting", self.password)

    def post(self, email, password=None, **extra):
        data = {"email": email, "password": password or self.password, **extra}
        return self.client.post(reverse("login"), data)

    def assertNotSignedIn(self, response, message):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, message)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_page_posts_every_form_field(self):
        html = self.client.get(reverse("login")).content.decode()
        self.assertIn('<form method="post"', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        for name in ("email", "password", "remember"):
            with self.subTest(name=name):
                self.assertIn(f'name="{name}"', html)

    def test_active_user_signs_in(self):
        response = self.post("active@example.com")
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.client.session["_auth_user_id"], str(self.active.pk))

    def test_email_is_case_insensitive(self):
        self.assertRedirects(self.post("ACTIVE@Example.com"), reverse("dashboard"))

    def test_inactive_user_told_to_activate(self):
        self.assertNotSignedIn(self.post("waiting@example.com"), LoginForm.NOT_ACTIVE)

    def test_inactive_status_hidden_without_correct_password(self):
        response = self.post("waiting@example.com", "wrong-password")
        self.assertNotSignedIn(response, LoginForm.INVALID_CREDENTIALS)
        self.assertNotContains(response, LoginForm.NOT_ACTIVE)

    def test_wrong_password_and_unknown_email_get_same_error(self):
        for response in (
            self.post("active@example.com", "wrong-password"),
            self.post("nobody@example.com"),
        ):
            self.assertNotSignedIn(response, LoginForm.INVALID_CREDENTIALS)

    def test_session_ends_with_browser_unless_remembered(self):
        self.post("active@example.com")
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.client.post(reverse("logout"))
        self.post("active@example.com", remember="on")
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_signed_in_user_is_sent_to_dashboard(self):
        self.client.force_login(self.active)
        self.assertRedirects(self.client.get(reverse("login")), reverse("dashboard"))

    def test_deactivated_user_loses_session(self):
        self.client.force_login(self.active)
        User.objects.filter(pk=self.active.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)

    def test_sign_out_ends_session(self):
        self.client.force_login(self.active)
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn(f'action="{reverse("logout")}"', html)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_sign_out_requires_post(self):
        self.client.force_login(self.active)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_post_without_csrf_token_rejected(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("login"), {"email": "active@example.com", "password": self.password}
        )
        self.assertEqual(response.status_code, 403)

    def test_returns_to_requested_page_after_sign_in(self):
        target = reverse("my_plants")
        page = self.client.get(f"{reverse('login')}?next={target}")
        self.assertContains(page, f'name="next" value="{target}"')
        self.assertRedirects(self.post("active@example.com", next=target), target)

    def test_next_to_another_site_is_ignored(self):
        for target in ("https://evil.example.com/", "//evil.example.com/"):
            with self.subTest(target=target):
                response = self.post("active@example.com", next=target)
                self.assertRedirects(response, reverse("dashboard"))
                self.client.post(reverse("logout"))

    def test_failed_sign_in_keeps_next(self):
        target = reverse("care_schedule")
        response = self.post("active@example.com", "wrong-password", next=target)
        self.assertContains(response, f'name="next" value="{target}"')


class AccessTests(TestCase):
    public_pages = ["home", "explore", "care_guides", "about", "style_guide", "login", "register"]

    def test_public_pages_open_without_signing_in(self):
        for name in self.public_pages:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_app_pages_send_visitors_to_sign_in(self):
        private = [p for p in urlpatterns if p.name not in self.public_pages + ["logout"]]
        self.assertIn("dashboard", [p.name for p in private])
        for pattern in private:
            name = pattern.name
            with self.subTest(page=name):
                url = reverse(name, args=[1] if "<int:pk>" in str(pattern.pattern) else None)
                self.assertRedirects(
                    self.client.get(url), f"{reverse('login')}?next={url}"
                )

    def test_header_shows_signed_in_user(self):
        user = User.objects.create_user(
            "jane@example.com", "Jane van Doe", "mossy-Fern-42!", is_active=True
        )
        self.client.force_login(user)
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn(">JD</div>", html)
        self.assertIn(", Jane 🌿", html)
        self.assertNotIn("Alex", html)


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com", "Admin", "mossy-Fern-42!")
        self.member = User.objects.create_user("member@example.com", "Member", "mossy-Fern-42!")
        self.client.force_login(self.admin)

    def test_admin_pages_render(self):
        urls = [
            reverse("admin:plantcare_user_changelist"),
            reverse("admin:plantcare_user_add"),
            reverse("admin:plantcare_user_change", args=[self.member.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_can_activate_user(self):
        url = reverse("admin:plantcare_user_change", args=[self.member.pk])
        response = self.client.post(url, {
            "email": self.member.email,
            "full_name": self.member.full_name,
            "role": self.member.role,
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_regular_user_cannot_open_admin(self):
        self.member.is_active = True
        self.member.save()
        self.client.force_login(self.member)
        response = self.client.get(reverse("admin:plantcare_user_changelist"))
        self.assertEqual(response.status_code, 302)


class PageRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "page@example.com", "Page Tester", "mossy-Fern-42!", is_active=True
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_every_page_renders(self):
        # logout is POST only; login sends signed-in users on to the dashboard.
        plant = Plant.objects.create(
            created_user=self.user, name="Fern", planting_date=date(2026, 1, 1)
        )
        species = PlantSpecies.objects.create(
            common_name="Fern", scientific_name="Nephrolepis exaltata",
            category="indoor", difficulty="easy", light="medium", watering="weekly",
        )
        reminder = WaterReminder.objects.create(plant=plant, next_due_date=date(2026, 1, 1))
        case = HealthCase.objects.create(plant=plant, title="Rust", next_check_date=date(2026, 1, 1))
        args = {"plant_edit": [plant.pk], "plant_view": [plant.pk], "species_edit": [species.pk],
                "water_reminder_edit": [reminder.pk], "health_case": [case.pk]}
        # The care task and water reminder actions are POST only too.
        post_only = (
            "logout", "login", "care_task_add", "care_task_complete", "care_task_delete",
            "care_auto_plan", "plant_replan", "water_reminder_auto", "water_reminder_water_all",
            "water_reminder_water", "water_reminder_toggle", "water_reminder_delete",
            "health_check_new", "health_case_update", "health_case_issue", "health_case_reanalyse",
            "health_case_resolve", "health_case_frequency", "health_case_delete",
        )
        pages = [pattern for pattern in urlpatterns if pattern.name not in post_only]
        for pattern in pages:
            with self.subTest(page=pattern.name):
                url = reverse(pattern.name, args=args.get(pattern.name))
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_sidebar_marks_current_page_active(self):
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn('class="side-link active" data-nav="dashboard"', html)
        self.assertIn('class="side-link" data-nav="settings"', html)

    def test_header_receives_page_values(self):
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn(">My Dashboard</div>", html)

    def test_header_has_no_search_box(self):
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertNotIn('data-field="search-box"', html)

    def test_my_plants_and_library_links_are_not_mixed_up(self):
        plant = Plant.objects.create(
            created_user=self.user, name="Fern", planting_date=date(2026, 1, 1)
        )
        plants = self.client.get(reverse("my_plants")).content.decode()
        library = self.client.get(reverse("library")).content.decode()
        self.assertIn(f'href="{reverse("plant_view", args=[plant.pk])}"', plants)
        self.assertIn(f'href="{reverse("library_view")}"', library)


class PlantCreateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "grower@example.com", "Grower", "mossy-Fern-42!", is_active=True
        )
        cls.species = PlantSpecies.objects.create(
            common_name="Swiss Cheese Plant", scientific_name="Monstera deliciosa",
            category="tropical", difficulty="easy", light="bright_indirect", watering="weekly",
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.valid = {
            "name": "Monstera",
            "nickname": "Monty",
            "plant_species": self.species.pk,
            "planting_date": "2026-03-01",
            "check_interval_days": "5",
            "status": "healthy",
        }

    def test_valid_post_creates_plant_for_current_user(self):
        response = self.client.post(reverse("plant_add"), self.valid, follow=True)
        self.assertRedirects(response, reverse("my_plants"))
        plant = Plant.objects.get()
        self.assertEqual(plant.created_user, self.user)
        self.assertEqual(plant.plant_species, self.species)
        self.assertEqual(plant.nickname, "Monty")
        self.assertEqual(plant.planting_date, date(2026, 3, 1))
        self.assertEqual(plant.check_interval_days, 5)
        self.assertContains(response, "Monstera was added to your plants.")

    def test_species_is_optional(self):
        self.valid["plant_species"] = ""
        self.client.post(reverse("plant_add"), self.valid)
        self.assertIsNone(Plant.objects.get().plant_species)

    def test_invalid_submissions_rejected(self):
        future = (timezone.localdate() + timedelta(days=1)).isoformat()
        cases = {
            "name": "",
            "planting_date": future,
            "check_interval_days": "0",
            "status": "dead",
            "plant_species": "9999",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                response = self.client.post(reverse("plant_add"), {**self.valid, field: value})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors.get(field))
        self.assertFalse(Plant.objects.exists())

    def test_post_cannot_assign_plant_to_another_user(self):
        other = User.objects.create_user("other@example.com", "Other", "x-Pass-123!", is_active=True)
        self.client.post(reverse("plant_add"), {**self.valid, "created_user": other.pk})
        self.assertEqual(Plant.objects.get().created_user, self.user)


class PlantListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "lister@example.com", "Lister", "mossy-Fern-42!", is_active=True
        )
        other = User.objects.create_user("o@example.com", "O", "mossy-Fern-42!", is_active=True)
        make = lambda **kw: Plant.objects.create(planting_date=date(2026, 1, 1), **kw)
        make(created_user=cls.user, name="Aloe", status="healthy")
        make(created_user=cls.user, name="Basil", nickname="Pesto", status="attention")
        make(created_user=cls.user, name="Cactus", status="critical")
        make(created_user=other, name="Not Mine")

    def setUp(self):
        self.client.force_login(self.user)

    def names(self, **params):
        response = self.client.get(reverse("my_plants"), params)
        return [p.name for p in response.context["page"].object_list]

    def test_lists_only_own_plants(self):
        self.assertEqual(self.names(), ["Aloe", "Basil", "Cactus"])

    def test_stats(self):
        stats = self.client.get(reverse("my_plants")).context["stats"]
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["healthy"], 1)
        self.assertEqual(stats["attention"], 2)

    def test_search_filter_and_sort(self):
        self.assertEqual(self.names(q="pesto"), ["Basil"])
        self.assertEqual(self.names(status="critical"), ["Cactus"])
        self.assertEqual(self.names(sort="-name"), ["Cactus", "Basil", "Aloe"])
        self.assertEqual(self.names(sort="bogus"), ["Aloe", "Basil", "Cactus"])

    def test_empty_state(self):
        self.assertContains(self.client.get(reverse("my_plants"), {"q": "zzz"}), "No plants match")

    def test_pagination_keeps_filters(self):
        for i in range(10):
            Plant.objects.create(created_user=self.user, name=f"Z{i:02}", planting_date=date(2026, 1, 1))
        response = self.client.get(reverse("my_plants"), {"sort": "name"})
        self.assertEqual(len(response.context["page"].object_list), 8)
        self.assertContains(response, "?sort=name&amp;page=2")


class PlantImageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "photo@example.com", "Photo", "mossy-Fern-42!", is_active=True
        )

    def setUp(self):
        import shutil, tempfile
        from django.test import override_settings
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        self.client.force_login(self.user)
        self.data = {
            "name": "Ivy", "planting_date": "2026-01-01",
            "check_interval_days": "7", "status": "healthy",
        }

    def png(self, name="ivy.png"):
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (4, 4), "green").save(buf, "PNG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")

    def test_upload_saves_image_and_shows_on_list(self):
        self.client.post(reverse("plant_add"), {**self.data, "image": self.png()})
        plant = Plant.objects.get()
        self.assertTrue(plant.image.name.startswith("plants/"))
        self.assertContains(self.client.get(reverse("my_plants")), plant.image.url)

    def test_non_image_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        response = self.client.post(reverse("plant_add"), {**self.data, "image": bad})
        self.assertTrue(response.context["form"].errors.get("image"))
        self.assertFalse(Plant.objects.exists())

    def test_oversized_image_rejected(self):
        from unittest import mock
        from .forms import PlantForm
        with mock.patch.object(PlantForm, "MAX_IMAGE_SIZE", 10):
            response = self.client.post(reverse("plant_add"), {**self.data, "image": self.png()})
        self.assertIn("5 MB", str(response.context["form"].errors["image"]))

    def test_image_is_optional(self):
        self.client.post(reverse("plant_add"), self.data)
        self.assertFalse(Plant.objects.get().image)


class PlantEditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "editor@example.com", "Editor", "mossy-Fern-42!", is_active=True
        )
        cls.other = User.objects.create_user(
            "nosy@example.com", "Nosy", "mossy-Fern-42!", is_active=True
        )

    def setUp(self):
        import shutil, tempfile
        from django.test import override_settings
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        self.client.force_login(self.user)
        self.plant = Plant.objects.create(
            created_user=self.user, name="Ivy", nickname="Ive",
            planting_date=date(2026, 2, 3), check_interval_days=4, status="healthy",
        )
        self.url = reverse("plant_edit", args=[self.plant.pk])
        self.data = {
            "name": "English Ivy", "nickname": "", "planting_date": "2026-02-10",
            "check_interval_days": "10", "status": "attention",
        }

    def png(self, name="ivy.png"):
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (4, 4), "green").save(buf, "PNG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")

    def test_form_is_prefilled(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('value="Ivy"', html)
        self.assertIn('value="Ive"', html)
        self.assertIn('value="2026-02-03"', html)
        self.assertIn('value="4"', html)
        self.assertIn('value="healthy" checked', html)
        self.assertIn("Save Changes", html)

    def test_valid_post_updates_plant(self):
        response = self.client.post(self.url, self.data, follow=True)
        self.assertRedirects(response, reverse("my_plants"))
        self.assertContains(response, "English Ivy was updated.")
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.name, "English Ivy")
        self.assertEqual(self.plant.nickname, "")
        self.assertEqual(self.plant.planting_date, date(2026, 2, 10))
        self.assertEqual(self.plant.check_interval_days, 10)
        self.assertEqual(self.plant.status, "attention")
        self.assertEqual(self.plant.created_user, self.user)

    def test_invalid_post_keeps_saved_values_in_header(self):
        response = self.client.post(self.url, {**self.data, "name": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("name"))
        self.assertContains(response, 'data-field="subtitle">Ivy<')
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.name, "Ivy")

    def test_other_users_cannot_view_or_edit(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 404)
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.name, "Ivy")

    def test_cannot_reassign_owner(self):
        self.client.post(self.url, {**self.data, "created_user": self.other.pk})
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.created_user, self.user)

    def test_keep_replace_and_remove_photo(self):
        self.client.post(self.url, {**self.data, "image": self.png("a.png")})
        self.plant.refresh_from_db()
        first = self.plant.image.name
        storage = self.plant.image.storage
        self.assertTrue(storage.exists(first))

        # No new file: photo is kept.
        self.client.post(self.url, self.data)
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.image.name, first)
        self.assertContains(self.client.get(self.url), "Remove current photo")

        # New file: replaced, old file deleted.
        self.client.post(self.url, {**self.data, "image": self.png("b.png")})
        self.plant.refresh_from_db()
        second = self.plant.image.name
        self.assertNotEqual(second, first)
        self.assertFalse(storage.exists(first))

        # Remove checkbox: cleared, file deleted.
        self.client.post(self.url, {**self.data, "image-clear": "on"})
        self.plant.refresh_from_db()
        self.assertFalse(self.plant.image)
        self.assertFalse(storage.exists(second))

    def test_list_links_to_edit(self):
        self.assertContains(self.client.get(reverse("my_plants")), f'href="{self.url}"')


class SpeciesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "species@example.com", "Species Keeper", "mossy-Fern-42!", is_active=True
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.data = {
            "common_name": " Snake Plant ", "scientific_name": "Dracaena trifasciata",
            "category": "indoor", "difficulty": "very_easy", "light": "low_to_bright",
            "watering": "biweekly", "fertilizing": "monthly",
            "special_features": ["air_purifying", "toxic"],
        }

    def make(self, **kw):
        fields = {
            "common_name": "Monstera", "scientific_name": "Monstera deliciosa",
            "category": "tropical", "difficulty": "easy", "light": "bright_indirect",
            "watering": "weekly",
        }
        return PlantSpecies.objects.create(**{**fields, **kw})

    def test_add_creates_species(self):
        response = self.client.post(reverse("species_add"), self.data, follow=True)
        self.assertRedirects(response, reverse("species"))
        self.assertContains(response, "Snake Plant was added")
        species = PlantSpecies.objects.get()
        self.assertEqual(species.common_name, "Snake Plant")
        self.assertEqual(species.special_features, "air_purifying,toxic")

    def test_add_requires_fields(self):
        response = self.client.post(reverse("species_add"), {"common_name": ""})
        errors = response.context["form"].errors
        for field in ("common_name", "scientific_name", "category", "difficulty", "light", "watering", "fertilizing"):
            with self.subTest(field=field):
                self.assertIn(field, errors)
        self.assertFalse(PlantSpecies.objects.exists())

    def test_scientific_name_unique_ignoring_case(self):
        self.make(scientific_name="Dracaena Trifasciata")
        response = self.client.post(reverse("species_add"), self.data)
        self.assertIn("scientific_name", response.context["form"].errors)
        self.assertEqual(PlantSpecies.objects.count(), 1)

    def test_edit_is_prefilled_and_saves(self):
        species = self.make(special_features="edible")
        url = reverse("species_edit", args=[species.pk])
        html = self.client.get(url).content.decode()
        self.assertIn('value="Monstera"', html)
        self.assertIn('value="tropical" selected', html)
        self.assertIn('value="edible" checked', html)
        self.assertIn("Save Changes", html)

        response = self.client.post(url, {**self.data, "scientific_name": "Monstera deliciosa"})
        self.assertRedirects(response, reverse("species"))
        species.refresh_from_db()
        self.assertEqual(species.common_name, "Snake Plant")
        self.assertEqual(species.watering, "biweekly")

    def test_edit_missing_species_is_404(self):
        self.assertEqual(self.client.get(reverse("species_edit", args=[999])).status_code, 404)

    def test_list_filters_and_counts(self):
        self.make()
        self.make(common_name="Aloe", scientific_name="Aloe vera", category="succulent", light="full_sun")
        response = self.client.get(reverse("species"))
        self.assertEqual(response.context["stats"]["total"], 2)
        self.assertContains(response, "Monstera")
        response = self.client.get(reverse("species"), {"category": "succulent"})
        names = [s.common_name for s in response.context["page"].object_list]
        self.assertEqual(names, ["Aloe"])
        response = self.client.get(reverse("species"), {"q": "deliciosa"})
        names = [s.common_name for s in response.context["page"].object_list]
        self.assertEqual(names, ["Monstera"])

    def test_soil_type_and_flower_color_save_as_lists(self):
        data = {
            **self.data,
            "soil_type": [" Loam ", "", "Perlite mix", "loam"],
            "flower_color": ["White", "Pink"],
        }
        self.client.post(reverse("species_add"), data)
        species = PlantSpecies.objects.get()
        # Blanks and case-insensitive duplicates are dropped; order is kept.
        self.assertEqual(species.soil_type, ["Loam", "Perlite mix"])
        self.assertEqual(species.flower_color, ["White", "Pink"])

    def test_list_fields_default_to_empty(self):
        self.client.post(reverse("species_add"), self.data)
        species = PlantSpecies.objects.get()
        self.assertEqual(species.soil_type, [])
        self.assertEqual(species.flower_color, [])

    def test_edit_shows_one_input_per_list_value(self):
        species = self.make(soil_type=["Loam", "Bark"], flower_color=["Red"])
        html = self.client.get(reverse("species_edit", args=[species.pk])).content.decode()
        self.assertIn('name="soil_type" class="input" value="Loam"', html)
        self.assertIn('name="soil_type" class="input" value="Bark"', html)
        self.assertIn('name="flower_color" class="input" value="Red"', html)

        url = reverse("species_edit", args=[species.pk])
        self.client.post(url, {**self.data, "scientific_name": "Monstera deliciosa",
                               "soil_type": ["Bark"], "flower_color": []})
        species.refresh_from_db()
        self.assertEqual(species.soil_type, ["Bark"])
        self.assertEqual(species.flower_color, [])

    def test_list_item_too_long_is_rejected(self):
        response = self.client.post(
            reverse("species_add"), {**self.data, "flower_color": ["x" * 61]}
        )
        self.assertIn("flower_color", response.context["form"].errors)
        self.assertFalse(PlantSpecies.objects.exists())


class PlantViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "viewer@example.com", "Viewer", "mossy-Fern-42!", is_active=True
        )
        cls.other = User.objects.create_user(
            "stranger@example.com", "Stranger", "mossy-Fern-42!", is_active=True
        )
        cls.species = PlantSpecies.objects.create(
            common_name="Swiss Cheese Plant", scientific_name="Monstera deliciosa",
            category="tropical", difficulty="easy", light="bright_indirect",
            watering="weekly", soil_type=["Peat", "Perlite"], flower_color=["Cream"],
            special_features="toxic,air_purifying", family="Araceae",
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.plant = Plant.objects.create(
            created_user=self.user, plant_species=self.species, name="Monty",
            nickname="Big M", planting_date=date(2025, 6, 1), check_interval_days=5,
            status="attention",
        )
        self.url = reverse("plant_view", args=[self.plant.pk])

    def test_shows_plant_and_species_details(self):
        html = self.client.get(self.url).content.decode()
        for text in ("Monty", "Big M", "Monstera deliciosa", "Needs Attention",
                     "Bright Indirect", "Peat, Perlite", "Cream", "Araceae",
                     "Toxic to Pets", "Air Purifying", "Jun 1, 2025",
                     f'href="{reverse("plant_edit", args=[self.plant.pk])}"'):
            with self.subTest(text=text):
                self.assertIn(text, html)

    def test_shows_care_logs_counts_and_open_tasks(self):
        now = timezone.now()
        CareLog.objects.create(plant=self.plant, activity="watering", performed_at=now - timedelta(days=2))
        CareLog.objects.create(plant=self.plant, activity="watering", performed_at=now - timedelta(days=9))
        CareLog.objects.create(plant=self.plant, activity="fertilizing", performed_at=now - timedelta(days=4), notes="Half strength")
        CareTask.objects.create(plant=self.plant, kind="fertilize", due_date=timezone.localdate() + timedelta(days=3))
        CareTask.objects.create(plant=self.plant, kind="prune", due_date=timezone.localdate(), completed_at=now)
        response = self.client.get(self.url)
        self.assertEqual(response.context["times_watered"], 2)
        self.assertEqual(response.context["care_count"], 3)
        self.assertEqual([t.kind for t in response.context["upcoming_tasks"]], ["fertilize"])
        self.assertContains(response, "Half strength")
        self.assertNotContains(response, "No care activity logged")

    def test_plant_without_species(self):
        self.plant.plant_species = None
        self.plant.save()
        response = self.client.get(self.url)
        self.assertContains(response, "No species linked")
        self.assertContains(response, "Link a Species")
        self.assertContains(response, "No care activity logged")

    def test_other_users_get_404(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_missing_plant_is_404(self):
        self.assertEqual(self.client.get(reverse("plant_view", args=[999])).status_code, 404)


class PlantFlowerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "flowers@example.com", "Flora", "mossy-Fern-42!", is_active=True
        )
        cls.species = PlantSpecies.objects.create(
            common_name="Hibiscus", scientific_name="Hibiscus rosa-sinensis",
            category="flowering", difficulty="easy", light="full_sun",
            watering="every_2_3_days", flower_color=["Red", "Pink"],
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.data = {
            "name": "Hibi", "plant_species": self.species.pk,
            "planting_date": "2026-01-01", "check_interval_days": "3", "status": "healthy",
        }

    def test_flowering_plant_saves_colors(self):
        self.client.post(reverse("plant_add"), {
            **self.data, "has_flowers": "on", "flower_colors": ["Red", " ", "Light Pink"],
        })
        plant = Plant.objects.get()
        self.assertTrue(plant.has_flowers)
        self.assertEqual(plant.flower_colors, ["Red", "Light Pink"])
        self.assertEqual(plant.flower_swatches, [("Red", "red"), ("Light Pink", "lightpink")])

    def test_flowering_plant_needs_a_color(self):
        response = self.client.post(reverse("plant_add"), {**self.data, "has_flowers": "on"})
        self.assertIn("flower_colors", response.context["form"].errors)
        self.assertFalse(Plant.objects.exists())

    def test_colors_dropped_when_not_flowering(self):
        self.client.post(reverse("plant_add"), {**self.data, "flower_colors": ["Red"]})
        plant = Plant.objects.get()
        self.assertFalse(plant.has_flowers)
        self.assertEqual(plant.flower_colors, [])

    def test_form_offers_species_colors(self):
        html = self.client.get(reverse("plant_add")).content.decode()
        self.assertIn('id="speciesFlowerColors"', html)
        self.assertIn(f'"{self.species.pk}": ["Red", "Pink"]', html)

    def test_colors_shown_on_view_and_list(self):
        plant = Plant.objects.create(
            created_user=self.user, name="Hibi", planting_date=date(2026, 1, 1),
            has_flowers=True, flower_colors=["Red", "Sunset #1"],
        )
        view = self.client.get(reverse("plant_view", args=[plant.pk])).content.decode()
        self.assertIn("background:red;", view)
        self.assertIn("Sunset #1", view)
        self.assertNotIn("background:sunset", view)
        self.assertIn("Yes &middot; Red, Sunset #1", view)
        self.assertIn("background:red;", self.client.get(reverse("my_plants")).content.decode())


class CareScheduleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "gardener@example.com", "Gardener", "mossy-Fern-42!", is_active=True
        )
        cls.other = User.objects.create_user(
            "nosy@example.com", "Nosy", "mossy-Fern-42!", is_active=True
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.plant = Plant.objects.create(
            created_user=self.user, name="Fern", planting_date=date(2026, 1, 1)
        )
        self.url = reverse("care_schedule")

    def task(self, days=0, **kw):
        kw.setdefault("kind", "water")
        plant = kw.pop("plant", self.plant)
        return CareTask.objects.create(
            plant=plant, due_date=self.today + timedelta(days=days), **kw
        )

    def test_stats_count_only_open_tasks_of_this_user(self):
        self.task(0)
        self.task(0, completed_at=timezone.now())
        self.task(-3)
        theirs = Plant.objects.create(
            created_user=self.other, name="Cactus", planting_date=date(2026, 1, 1)
        )
        self.task(0, plant=theirs)
        stats = self.client.get(self.url).context["stats"]
        self.assertEqual(stats["today"], 1)
        self.assertEqual(stats["overdue"], 1)
        # The overdue task counts toward this week only if it fell after Sunday.
        days_since_sunday = (self.today.weekday() + 1) % 7
        self.assertEqual(stats["week"], 1 + int(days_since_sunday >= 3))

    def test_week_view_runs_sunday_to_saturday_with_tasks(self):
        task = self.task(0, kind="fertilize")
        done = self.task(0, completed_at=timezone.now())
        weeks = self.client.get(self.url).context["weeks"]
        self.assertEqual(len(weeks), 1)
        self.assertEqual(weeks[0][0]["date"].weekday(), 6)  # Sunday
        self.assertEqual(len(weeks[0]), 7)
        today = next(c for c in weeks[0] if c["is_today"])
        self.assertEqual(today["tasks"], [task, done])  # open before done

    def test_month_view_covers_whole_month(self):
        response = self.client.get(self.url, {"view": "month", "date": "2026-02-10"})
        days = [c["date"] for week in response.context["weeks"] for c in week]
        self.assertEqual(days[0], date(2026, 2, 1))  # Feb 1 2026 is a Sunday
        self.assertEqual(days[-1], date(2026, 2, 28))
        self.assertEqual(response.context["range_label"], "February 2026")
        self.assertEqual(response.context["prev_date"], date(2026, 1, 1))
        self.assertEqual(response.context["next_date"], date(2026, 3, 1))

    def test_week_label_and_navigation(self):
        response = self.client.get(self.url, {"date": "2026-11-13"})
        self.assertEqual(response.context["range_label"], "Nov 8 – Nov 14, 2026")
        self.assertEqual(response.context["prev_date"], date(2026, 11, 1))
        self.assertEqual(response.context["next_date"], date(2026, 11, 15))

    def test_list_view_and_filters(self):
        self.task(1, kind="water")
        prune = self.task(2, kind="prune")
        response = self.client.get(self.url, {"view": "list", "kind": "prune"})
        self.assertEqual(response.context["weeks"], [])
        self.assertEqual(list(response.context["page"].object_list), [prune])

    def test_status_filter(self):
        open_task = self.task(1)
        done = self.task(0, completed_at=timezone.now())
        listed = lambda status: list(
            self.client.get(self.url, {"status": status}).context["page"].object_list
        )
        self.assertEqual(listed("open"), [open_task])
        self.assertEqual(listed("done"), [done])
        self.assertEqual(listed("all"), [open_task, done])

    def test_bad_query_values_fall_back_to_defaults(self):
        response = self.client.get(self.url, {
            "view": "year", "date": "nope", "kind": "x", "plant": "99", "status": "?",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view"], "week")
        self.assertEqual(response.context["anchor"], self.today)
        self.assertEqual(response.context["plant_id"], "")
        self.assertEqual(response.context["status"], "open")

    def test_add_task(self):
        response = self.client.post(reverse("care_task_add"), {
            "plant": self.plant.pk, "kind": "fertilize",
            "due_date": (self.today + timedelta(days=3)).isoformat(),
            "repeat_every_days": "14", "notes": " Half strength ",
            "next": self.url + "?view=list",
        })
        self.assertRedirects(response, self.url + "?view=list")
        task = CareTask.objects.get()
        self.assertEqual(
            (task.plant, task.kind, task.repeat_every_days, task.notes),
            (self.plant, "fertilize", 14, "Half strength"),
        )

    def test_add_rejects_past_date_and_other_users_plant(self):
        theirs = Plant.objects.create(
            created_user=self.other, name="Cactus", planting_date=date(2026, 1, 1)
        )
        response = self.client.post(reverse("care_task_add"), {
            "plant": theirs.pk, "kind": "water",
            "due_date": (self.today - timedelta(days=1)).isoformat(),
            "next": self.url + "?view=month",
        })
        self.assertEqual(response.status_code, 200)
        errors = response.context["form"].errors
        self.assertIn("plant", errors)
        self.assertIn("due_date", errors)
        self.assertTrue(response.context["show_form"])
        self.assertEqual(response.context["next_url"], self.url + "?view=month")
        self.assertFalse(CareTask.objects.exists())

    def test_add_ignores_offsite_next(self):
        response = self.client.post(reverse("care_task_add"), {
            "plant": self.plant.pk, "kind": "water", "due_date": self.today.isoformat(),
            "next": "https://evil.example.com/",
        })
        self.assertRedirects(response, self.url)

    def test_complete_logs_care_and_schedules_repeat(self):
        task = self.task(0, kind="fertilize", repeat_every_days=7, notes="Diluted")
        response = self.client.post(reverse("care_task_complete", args=[task.pk]))
        self.assertRedirects(response, self.url)
        task.refresh_from_db()
        self.assertIsNotNone(task.completed_at)
        log = CareLog.objects.get()
        self.assertEqual((log.plant, log.activity, log.notes), (self.plant, "fertilizing", "Diluted"))
        follow_up = CareTask.objects.get(completed_at__isnull=True)
        self.assertEqual(follow_up.due_date, self.today + timedelta(days=7))
        self.assertEqual(follow_up.repeat_every_days, 7)

    def test_complete_twice_does_nothing_more(self):
        task = self.task(0, repeat_every_days=3)
        self.client.post(reverse("care_task_complete", args=[task.pk]))
        self.client.post(reverse("care_task_complete", args=[task.pk]))
        self.assertEqual(CareLog.objects.count(), 1)
        self.assertEqual(CareTask.objects.count(), 2)

    def test_delete_task(self):
        task = self.task(1)
        self.assertRedirects(self.client.post(reverse("care_task_delete", args=[task.pk])), self.url)
        self.assertFalse(CareTask.objects.exists())

    def test_actions_require_post_and_ownership(self):
        task = self.task(1)
        for name in ("care_task_complete", "care_task_delete"):
            with self.subTest(action=name):
                url = reverse(name, args=[task.pk])
                self.assertEqual(self.client.get(url).status_code, 405)
                self.client.force_login(self.other)
                self.assertEqual(self.client.post(url).status_code, 404)
                self.client.force_login(self.user)
        task.refresh_from_db()
        self.assertIsNone(task.completed_at)

    def test_page_renders_real_tasks_and_actions(self):
        task = self.task(0, notes="Bottom water")
        html = self.client.get(self.url).content.decode()
        self.assertIn("Bottom water", html)
        self.assertIn(f'action="{reverse("care_task_complete", args=[task.pk])}"', html)
        self.assertIn(f'action="{reverse("care_task_add")}"', html)
        self.assertNotIn("Fiddle Leaf Fig", html)  # no leftover mock-up data
        for view in ("month", "list"):
            with self.subTest(view=view):
                self.assertContains(self.client.get(self.url, {"view": view}), "Bottom water")


class CarePlanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "planner@example.com", "Planner", "mossy-Fern-42!", is_active=True
        )
        cls.other = User.objects.create_user(
            "nosy@example.com", "Nosy", "mossy-Fern-42!", is_active=True
        )
        cls.species = PlantSpecies.objects.create(
            common_name="Swiss Cheese Plant", scientific_name="Monstera deliciosa",
            category="tropical", difficulty="easy", light="bright_indirect",
            watering="weekly", fertilizing="monthly", growth_rate="fast",
        )
        cls.cactus = PlantSpecies.objects.create(
            common_name="Golden Barrel", scientific_name="Echinocactus grusonii",
            category="desert", difficulty="easy", light="full_sun",
            watering="biweekly", humidity="low", growth_rate="slow",
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.today = timezone.localdate()

    def make(self, species=None, **kw):
        return Plant.objects.create(
            created_user=kw.pop("user", self.user), plant_species=species,
            name=kw.pop("name", "Monty"), planting_date=date(2026, 1, 1), **kw
        )

    def plan_of(self, plant):
        return {t.kind: t for t in plant.tasks.filter(completed_at__isnull=True)}

    def test_analyse_uses_species_needs(self):
        from . import care_plan
        plan = {p.kind: p for p in care_plan.analyse(self.make(self.species), self.today)}
        self.assertEqual(plan["water"].every_days, 7)
        self.assertEqual(plan["water"].first_due, self.today)
        self.assertEqual(plan["fertilize"].every_days, 30)
        self.assertEqual(plan["fertilize"].first_due, self.today + timedelta(days=14))
        self.assertEqual(plan["prune"].every_days, 30)  # fast grower
        self.assertIn("Weekly watering for Swiss Cheese Plant", plan["water"].reason)

    def test_analyse_adjusts_for_sun_and_dry_air(self):
        from . import care_plan
        plan = {p.kind: p for p in care_plan.analyse(self.make(self.cactus), self.today)}
        self.assertEqual(plan["water"].every_days, round(14 * 0.8 * 0.9))  # 10
        self.assertIn("full sun", plan["water"].reason)
        self.assertIn("dry air", plan["water"].reason)
        self.assertEqual(plan["fertilize"].every_days, 90)  # slow grower, no species frequency
        self.assertEqual(plan["prune"].every_days, 120)

    def test_analyse_without_species_waters_on_check_interval(self):
        from . import care_plan
        plan = care_plan.analyse(self.make(check_interval_days=4), self.today)
        self.assertEqual([(p.kind, p.every_days) for p in plan], [("water", 4)])

    def test_adding_a_plant_creates_its_schedule(self):
        response = self.client.post(reverse("plant_add"), {
            "name": "Monty", "plant_species": self.species.pk,
            "planting_date": "2026-03-01", "check_interval_days": "5", "status": "healthy",
        }, follow=True)
        plant = Plant.objects.get(name="Monty")
        tasks = self.plan_of(plant)
        self.assertEqual(set(tasks), {"water", "fertilize", "prune"})
        self.assertTrue(all(t.auto_generated for t in tasks.values()))
        self.assertEqual(tasks["water"].repeat_every_days, 7)
        self.assertContains(response, "Care schedule created: Watering every 7 days")

    def test_changing_species_replans_but_keeps_manual_tasks(self):
        from . import care_plan
        plant = self.make(self.species)
        care_plan.apply(plant)
        manual = CareTask.objects.create(plant=plant, kind="water", due_date=self.today)
        self.client.post(reverse("plant_edit", args=[plant.pk]), {
            "name": "Monty", "plant_species": self.cactus.pk, "planting_date": "2026-01-01",
            "check_interval_days": "7", "status": "healthy",
        })
        auto = plant.tasks.filter(auto_generated=True)
        self.assertEqual(auto.count(), 3)
        self.assertEqual(auto.get(kind="water").repeat_every_days, 10)
        self.assertTrue(CareTask.objects.filter(pk=manual.pk).exists())

    def test_editing_other_fields_leaves_schedule_alone(self):
        from . import care_plan
        plant = self.make(self.species, check_interval_days=7)
        care_plan.apply(plant)
        CareTask.objects.filter(plant=plant, kind="water").update(due_date=self.today + timedelta(days=2))
        self.client.post(reverse("plant_edit", args=[plant.pk]), {
            "name": "Renamed", "plant_species": self.species.pk, "planting_date": "2026-01-01",
            "check_interval_days": "7", "status": "attention",
        })
        self.assertEqual(self.plan_of(plant)["water"].due_date, self.today + timedelta(days=2))

    def test_completing_auto_task_keeps_it_automatic(self):
        from . import care_plan
        plant = self.make(self.species)
        care_plan.apply(plant)
        water = plant.tasks.get(kind="water")
        self.client.post(reverse("care_task_complete", args=[water.pk]))
        follow_up = plant.tasks.get(kind="water", completed_at__isnull=True)
        self.assertTrue(follow_up.auto_generated)
        self.assertEqual(follow_up.due_date, self.today + timedelta(days=7))

    def test_replan_button_rebuilds_without_duplicates(self):
        plant = self.make(self.species)
        url = reverse("plant_replan", args=[plant.pk])
        self.client.post(url)
        response = self.client.post(url, follow=True)
        self.assertEqual(plant.tasks.count(), 3)
        self.assertContains(response, "Care schedule for Monty updated")
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_schedule_page_offers_and_creates_missing_schedules(self):
        planned = self.make(self.species, name="Planned")
        CareTask.objects.create(plant=planned, kind="water", due_date=self.today)
        bare = self.make(self.cactus, name="Bare")
        self.make(self.cactus, name="Theirs", user=self.other)
        response = self.client.get(reverse("care_schedule"))
        self.assertEqual(response.context["unplanned"], 1)
        self.assertContains(response, 'data-unplanned="1"')
        self.client.post(reverse("care_auto_plan"))
        self.assertEqual(bare.tasks.count(), 3)
        self.assertEqual(planned.tasks.count(), 1)  # already had a schedule
        self.assertFalse(Plant.objects.get(name="Theirs").tasks.exists())
        self.assertEqual(self.client.get(reverse("care_schedule")).context["unplanned"], 0)

    def calendar_days(self, kind, **params):
        """Dates showing a task of ``kind`` in the calendar for these params."""
        weeks = self.client.get(reverse("care_schedule"), params).context["weeks"]
        return [c["date"] for w in weeks for c in w if any(t.kind == kind for t in c["tasks"])]

    def test_daily_watering_shows_on_every_day(self):
        plant = self.make(self.species)
        CareTask.objects.create(plant=plant, kind="water", due_date=self.today, repeat_every_days=1)
        days = self.calendar_days("water", view="month")
        last = days[-1]
        self.assertEqual(days, [self.today + timedelta(days=i) for i in range((last - self.today).days + 1)])
        next_week = self.calendar_days("water", date=(self.today + timedelta(days=7)).isoformat())
        self.assertEqual(len(next_week), 7)  # all seven days of the following week

    def test_every_3_days_shows_every_third_day(self):
        plant = self.make(self.species)
        CareTask.objects.create(plant=plant, kind="water", due_date=self.today, repeat_every_days=3)
        next_week = (self.today + timedelta(days=30)).isoformat()
        days = self.calendar_days("water", view="month", date=next_week)
        self.assertTrue(days)
        for day in days:
            self.assertEqual((day - self.today).days % 3, 0)
        self.assertTrue(all(b - a == timedelta(days=3) for a, b in zip(days, days[1:])))

    def test_planned_repeats_are_not_saved_or_counted(self):
        plant = self.make(self.species)
        CareTask.objects.create(plant=plant, kind="water", due_date=self.today, repeat_every_days=1)
        response = self.client.get(reverse("care_schedule"), {"view": "month"})
        self.assertEqual(CareTask.objects.count(), 1)
        self.assertEqual(response.context["stats"]["today"], 1)
        self.assertEqual(len(response.context["page"].object_list), 1)
        self.assertContains(response, "data-planned")
        self.assertContains(response, "Every day")

    def test_overdue_repeat_counts_from_today_and_done_tasks_dont_repeat(self):
        plant = self.make(self.species)
        CareTask.objects.create(plant=plant, kind="water", due_date=self.today - timedelta(days=5), repeat_every_days=7)
        CareTask.objects.create(plant=plant, kind="prune", due_date=self.today, repeat_every_days=1,
                                completed_at=timezone.now())
        days = self.calendar_days("water", view="month", date=(self.today + timedelta(days=7)).isoformat())
        self.assertIn(self.today + timedelta(days=7), days)
        self.assertNotIn(self.today + timedelta(days=2), days)
        prune_days = self.calendar_days("prune", view="month")
        self.assertEqual(prune_days, [self.today])

    def test_calendar_cards_open_task_popup_with_actions(self):
        import re
        plant = self.make(self.species, name="Ctcus")
        task = CareTask.objects.create(plant=plant, kind="water", due_date=self.today,
                                       repeat_every_days=1, notes="Bottom water")
        html = self.client.get(reverse("care_schedule")).content.decode()
        self.assertIn('id="task-dialog"', html)
        cards = re.findall(r'<a [^>]*class="task-card".*?>', html, re.S)
        real = [c for c in cards if "data-planned" not in c]
        planned = [c for c in cards if "data-planned" in c]
        self.assertEqual(len(real), 1)
        self.assertIn(f'data-complete-url="{reverse("care_task_complete", args=[task.pk])}"', real[0])
        self.assertIn(f'data-delete-url="{reverse("care_task_delete", args=[task.pk])}"', real[0])
        self.assertIn('data-repeat="Every day"', real[0])
        self.assertIn('data-status="Due today"', real[0])
        self.assertTrue(planned)
        for card in planned:
            self.assertNotIn("data-complete-url", card)
            self.assertNotIn("data-delete-url", card)


class WaterReminderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "waterer@example.com", "Waterer", "mossy-Fern-42!", is_active=True
        )
        cls.other = User.objects.create_user(
            "nosy@example.com", "Nosy", "mossy-Fern-42!", is_active=True
        )
        cls.species = PlantSpecies.objects.create(
            common_name="Swiss Cheese Plant", scientific_name="Monstera deliciosa",
            category="tropical", difficulty="easy", light="bright_indirect", watering="weekly",
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.plant = Plant.objects.create(
            created_user=self.user, plant_species=self.species, name="Monty",
            planting_date=date(2026, 1, 1),
        )
        self.url = reverse("watering_schedule")

    def other_plant(self, name, **kw):
        return Plant.objects.create(
            created_user=kw.pop("user", self.user), name=name, planting_date=date(2026, 1, 1), **kw
        )

    def reminder(self, days=0, **kw):
        return WaterReminder.objects.create(
            plant=kw.pop("plant", self.plant),
            next_due_date=self.today + timedelta(days=days), **kw
        )

    def test_reminder_belongs_to_plant(self):
        r = self.reminder(frequency_days=3)
        self.assertEqual(r.plant, self.plant)
        self.assertEqual(list(self.plant.water_reminders.all()), [r])
        self.plant.delete()
        self.assertFalse(WaterReminder.objects.exists())

    def test_page_groups_reminders_and_counts_stats(self):
        overdue = self.reminder(-2)
        soon = self.reminder(3, plant=self.other_plant("Ivy"))
        later = self.reminder(20, plant=self.other_plant("Fig"))
        paused = self.reminder(0, is_active=False, plant=self.other_plant("Jade"))
        self.reminder(0, plant=self.other_plant("Cactus", user=self.other))
        response = self.client.get(self.url)
        sections = response.context["sections"]
        self.assertEqual(sections["due"], [overdue])
        self.assertEqual(sections["week"], [soon])
        self.assertEqual(sections["later"], [later])
        self.assertEqual(sections["paused"], [paused])
        self.assertEqual(response.context["stats"], {"due": 1, "week": 2, "recent": 0, "active": 3})
        self.assertContains(response, "Overdue since")
        self.assertNotContains(response, "Cactus")

    def test_show_filter_and_sort(self):
        self.reminder(3)
        response = self.client.get(self.url, {"show": "week", "sort": "name"})
        self.assertEqual(list(response.context["sections"]), ["week"])
        response = self.client.get(self.url, {"show": "bogus", "sort": "bogus"})
        self.assertEqual(response.context["show"], "")
        self.assertEqual(response.context["sort"], "due")

    def test_add_reminder_for_own_plant(self):
        response = self.client.post(reverse("water_reminder_add"), {
            "plant": self.plant.pk, "frequency_days": "5", "next_due_date": self.today.isoformat(),
            "reminder_time": "08:30", "method": "bottom", "amount_ml": "250",
            "notes": " Room-temperature water ", "is_active": "on",
        })
        self.assertRedirects(response, self.url)
        r = WaterReminder.objects.get()
        self.assertEqual((r.plant, r.frequency_days, r.method, r.amount_ml, r.notes),
                         (self.plant, 5, "bottom", 250, "Room-temperature water"))
        self.assertEqual(r.reminder_time.strftime("%H:%M"), "08:30")
        self.assertTrue(r.is_active)

    def test_add_rejects_other_users_plant_and_past_date(self):
        theirs = self.other_plant("Cactus", user=self.other)
        response = self.client.post(reverse("water_reminder_add"), {
            "plant": theirs.pk, "frequency_days": "0",
            "next_due_date": (self.today - timedelta(days=1)).isoformat(),
            "reminder_time": "08:30", "method": "top",
        })
        self.assertEqual(response.status_code, 200)
        errors = response.context["form"].errors
        for field in ("plant", "frequency_days", "next_due_date"):
            self.assertIn(field, errors)
        self.assertFalse(WaterReminder.objects.exists())

    def test_add_page_suggests_interval_from_species(self):
        response = self.client.get(reverse("water_reminder_add"), {"plant": self.plant.pk})
        self.assertEqual(response.context["suggestions"][str(self.plant.pk)], 7)
        self.assertEqual(response.context["form"].initial["frequency_days"], 7)

    def test_edit_keeps_past_due_date_and_blocks_others(self):
        r = self.reminder(-3, frequency_days=7)
        url = reverse("water_reminder_edit", args=[r.pk])
        self.assertContains(self.client.get(url), f'value="{r.next_due_date.isoformat()}"')
        response = self.client.post(url, {
            "plant": self.plant.pk, "frequency_days": "10",
            "next_due_date": r.next_due_date.isoformat(),
            "reminder_time": "07:00", "method": "mist",
        })
        self.assertRedirects(response, self.url)
        r.refresh_from_db()
        self.assertEqual((r.frequency_days, r.method, r.is_active), (10, "mist", False))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_mark_watered_logs_moves_due_date_and_ticks_schedule(self):
        r = self.reminder(-1, frequency_days=4, method="bottom", amount_ml=300)
        task = CareTask.objects.create(plant=self.plant, kind="water", due_date=self.today, repeat_every_days=4)
        response = self.client.post(reverse("water_reminder_water", args=[r.pk]))
        self.assertRedirects(response, self.url)
        r.refresh_from_db()
        self.assertEqual(r.next_due_date, self.today + timedelta(days=4))
        self.assertIsNotNone(r.last_watered_at)
        log = CareLog.objects.get()  # exactly one history entry
        self.assertEqual(log.activity, "watering")
        self.assertIn("300 ml", log.notes)
        task.refresh_from_db()
        self.assertIsNotNone(task.completed_at)
        self.assertTrue(CareTask.objects.filter(
            completed_at__isnull=True, due_date=self.today + timedelta(days=4)
        ).exists())

    def test_completing_schedule_watering_moves_reminder(self):
        r = self.reminder(0, frequency_days=5)
        task = CareTask.objects.create(plant=self.plant, kind="water", due_date=self.today)
        self.client.post(reverse("care_task_complete", args=[task.pk]))
        r.refresh_from_db()
        self.assertEqual(r.next_due_date, self.today + timedelta(days=5))
        self.assertEqual(CareLog.objects.count(), 1)

    def test_water_all_only_touches_due_active_reminders(self):
        due = self.reminder(0)
        future = self.reminder(3, plant=self.other_plant("Ivy"))
        paused = self.reminder(-1, is_active=False, plant=self.other_plant("Jade"))
        self.client.post(reverse("water_reminder_water_all"))
        for r in (due, future, paused):
            r.refresh_from_db()
        self.assertIsNotNone(due.last_watered_at)
        self.assertIsNone(future.last_watered_at)
        self.assertIsNone(paused.last_watered_at)

    def test_pause_resume_and_delete(self):
        r = self.reminder(-5)
        toggle = reverse("water_reminder_toggle", args=[r.pk])
        self.client.post(toggle)
        r.refresh_from_db()
        self.assertFalse(r.is_active)
        self.client.post(toggle)
        r.refresh_from_db()
        self.assertTrue(r.is_active)
        self.assertEqual(r.next_due_date, self.today)  # a resumed overdue reminder restarts today
        self.client.post(reverse("water_reminder_delete", args=[r.pk]))
        self.assertFalse(WaterReminder.objects.exists())

    def test_actions_require_post_and_ownership(self):
        r = self.reminder(0)
        for name in ("water_reminder_water", "water_reminder_toggle", "water_reminder_delete"):
            with self.subTest(action=name):
                url = reverse(name, args=[r.pk])
                self.assertEqual(self.client.get(url).status_code, 405)
                self.client.force_login(self.other)
                self.assertEqual(self.client.post(url).status_code, 404)
                self.client.force_login(self.user)
        self.assertTrue(WaterReminder.objects.filter(pk=r.pk, is_active=True, last_watered_at=None).exists())

    def test_offsite_next_is_ignored(self):
        r = self.reminder(0)
        response = self.client.post(
            reverse("water_reminder_water", args=[r.pk]), {"next": "//evil.example.com/"}
        )
        self.assertRedirects(response, self.url)

    def test_auto_create_reminders_for_plants_without_one(self):
        self.other_plant("Bare", check_interval_days=4)
        self.reminder(2)
        self.other_plant("Theirs", user=self.other)
        self.assertEqual(self.client.get(self.url).context["without_reminder"], 1)
        self.client.post(reverse("water_reminder_auto"))
        bare = WaterReminder.objects.get(plant__name="Bare")
        self.assertEqual((bare.frequency_days, bare.next_due_date), (4, self.today))
        self.assertEqual(self.plant.water_reminders.count(), 1)
        self.assertFalse(WaterReminder.objects.filter(plant__name="Theirs").exists())
        self.assertEqual(self.client.get(self.url).context["without_reminder"], 0)

    def test_empty_state(self):
        self.assertContains(self.client.get(self.url), "No watering reminders yet")


def _png(name="leaf.png", color=(40, 140, 60)):
    import io
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


AI_APHIDS = {
    "is_plant": True, "overall": "severe", "progress": "first",
    "summary": "Clusters of aphids on the new shoots.",
    "issues": [
        {"key": "aphids", "name": "Aphids", "confidence": "high",
         "evidence": "Green insects clustered on stem tips.",
         "organic_treatments": [
             {"name": "Neem Oil", "how": "duplicate of library entry"},
             {"name": "Garlic Spray", "how": "Blend 2 garlic bulbs in 1 litre of water, strain, spray weekly."},
         ],
         "prevention": "Check new growth weekly."},
        {"key": "other", "name": "Sooty Mould", "confidence": "low",
         "evidence": "Dark film on lower leaves.",
         "organic_treatments": [{"name": "Wipe Leaves", "how": "Wipe with soapy water."}],
         "prevention": "Control the aphids."},
    ],
}
AI_HEALTHY = {"is_plant": True, "overall": "healthy", "progress": "first",
              "summary": "Leaves look green and firm.", "issues": []}


class PlantHealthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "doctor@example.com", "Doctor", "mossy-Fern-42!", is_active=True
        )
        cls.other = User.objects.create_user(
            "nosy@example.com", "Nosy", "mossy-Fern-42!", is_active=True
        )

    def setUp(self):
        import shutil, tempfile
        from django.test import override_settings
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.plant = Plant.objects.create(
            created_user=self.user, name="Rosie", planting_date=date(2026, 1, 1)
        )

    def analyse_returns(self, result=None, error=None):
        from unittest import mock
        from . import health_ai
        kwargs = {"side_effect": health_ai.AnalysisError(error)} if error else {"return_value": result}
        patcher = mock.patch("plantcare.health_ai.analyse", **kwargs)
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    def post_check(self, **data):
        payload = {"plant": self.plant.pk, "image": _png(), "notes": "", "issue_key": "",
                   "other_issue": "", "severity": "moderate", "check_every_days": "7",
                   "action": "find", **data}
        return self.client.post(reverse("health_check_new"), payload)

    def test_page_renders_form_and_library(self):
        response = self.client.get(reverse("plant_health"))
        self.assertContains(response, 'action="/plant-health/check/"')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, "Find it from the photo")
        self.assertContains(response, "I know the issue")
        self.assertContains(response, "Powdery Mildew")

    def test_known_issue_starts_case_with_organic_plan(self):
        mocked = self.analyse_returns(AI_APHIDS)
        response = self.post_check(action="known", issue_key="aphids", severity="mild")
        mocked.assert_not_called()
        case = HealthCase.objects.get()
        self.assertRedirects(response, reverse("health_case", args=[case.pk]))
        self.assertEqual((case.title, case.issue_key, case.source, case.severity),
                         ("Aphids", "aphids", "user", "mild"))
        self.assertEqual(case.next_check_date, self.today + timedelta(days=7))
        self.assertEqual(case.checks.get().analysis_status, "skipped")
        task = CareTask.objects.get(kind="health")
        self.assertEqual((task.due_date, task.repeat_every_days), (case.next_check_date, 7))
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.status, "attention")
        page = self.client.get(response.url)
        self.assertContains(page, "Neem Oil")
        self.assertContains(page, "Mix 1–2 tablespoons per gallon of water")
        self.assertContains(page, "Insecticidal Soap")

    def test_known_issue_can_be_typed(self):
        self.post_check(action="known", other_issue="Leaf miner")
        self.assertEqual(HealthCase.objects.get().title, "Leaf miner")

    def test_known_issue_requires_an_issue(self):
        response = self.post_check(action="known")
        self.assertEqual(response.status_code, 200)
        self.assertIn("issue_key", response.context["form"].errors)
        self.assertFalse(HealthCheck.objects.exists())

    def test_find_issue_from_photo(self):
        mocked = self.analyse_returns(AI_APHIDS)
        response = self.post_check(notes="Sticky leaves")
        self.assertEqual(mocked.call_args.kwargs["notes"], "Sticky leaves")
        case = HealthCase.objects.get()
        self.assertEqual((case.title, case.issue_key, case.source, case.severity),
                         ("Aphids", "aphids", "ai", "severe"))
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.status, "critical")
        page = self.client.get(response.url)
        self.assertContains(page, "Clusters of aphids on the new shoots.")
        self.assertContains(page, "Green insects clustered on stem tips.")
        self.assertContains(page, "Garlic Spray")  # extra suggestion from the analysis
        names = [t["name"] for t in page.context["treatments"]]
        self.assertEqual(names.count("Neem Oil"), 1)  # no duplicates
        self.assertContains(page, "Sooty Mould")  # other possible issue

    def test_healthy_photo_needs_no_case(self):
        self.analyse_returns(AI_HEALTHY)
        response = self.post_check()
        self.assertRedirects(response, reverse("plant_health"))
        self.assertFalse(HealthCase.objects.exists())
        check = HealthCheck.objects.get()
        self.assertIsNone(check.case)
        self.assertContains(self.client.get(reverse("plant_health")), "Recent Healthy Checks")

    def test_failed_analysis_keeps_photo_and_lets_user_pick_issue(self):
        self.analyse_returns(error="Photo analysis isn't set up.")
        response = self.post_check()
        case = HealthCase.objects.get()
        self.assertEqual((case.title, case.source), ("Unidentified issue", "unknown"))
        self.assertEqual(case.checks.get().analysis_status, "failed")
        page = self.client.get(response.url)
        self.assertContains(page, "Photo analysis isn&#x27;t set up.")
        self.client.post(reverse("health_case_issue", args=[case.pk]),
                         {"issue_key": "powdery_mildew", "severity": "mild"})
        case.refresh_from_db()
        self.assertEqual((case.title, case.source, case.severity), ("Powdery Mildew", "user", "mild"))
        self.assertContains(self.client.get(response.url), "Baking Soda Spray")

    def test_photo_update_compares_and_tracks_progress(self):
        self.post_check(action="known", issue_key="aphids")
        case = HealthCase.objects.get()
        mocked = self.analyse_returns({**AI_APHIDS, "overall": "mild", "progress": "better"})
        response = self.client.post(reverse("health_case_update", args=[case.pk]),
                                    {"image": _png("week2.png"), "progress": "", "notes": "Sprayed", "analyse": "on"})
        self.assertRedirects(response, reverse("health_case", args=[case.pk]))
        self.assertIsNotNone(mocked.call_args.kwargs["previous_image"])
        case.refresh_from_db()
        self.assertEqual((case.status, case.severity), ("improving", "mild"))
        latest = case.checks.order_by("-created_at").first()
        self.assertEqual((latest.progress, latest.notes), ("better", "Sprayed"))
        self.assertEqual(CareTask.objects.filter(kind="health", completed_at__isnull=True).count(), 1)
        self.assertEqual(CareLog.objects.filter(activity="health").count(), 2)

    def test_photo_update_without_analysis_uses_chosen_progress(self):
        self.post_check(action="known", issue_key="aphids")
        case = HealthCase.objects.get()
        mocked = self.analyse_returns(AI_APHIDS)
        self.client.post(reverse("health_case_update", args=[case.pk]),
                         {"image": _png(), "progress": "worse"})
        mocked.assert_not_called()
        self.assertEqual(case.checks.order_by("-created_at").first().progress, "worse")

    def test_resolve_and_reopen(self):
        self.post_check(action="known", issue_key="rust", severity="severe")
        case = HealthCase.objects.get()
        url = reverse("health_case_resolve", args=[case.pk])
        self.client.post(url)
        case.refresh_from_db()
        self.plant.refresh_from_db()
        self.assertEqual(case.status, "resolved")
        self.assertEqual(self.plant.status, "healthy")
        self.assertFalse(CareTask.objects.filter(kind="health", completed_at__isnull=True).exists())
        self.client.post(url)
        case.refresh_from_db()
        self.plant.refresh_from_db()
        self.assertEqual(case.status, "active")
        self.assertEqual(self.plant.status, "critical")
        self.assertTrue(CareTask.objects.filter(kind="health", completed_at__isnull=True).exists())

    def test_change_update_frequency(self):
        self.post_check(action="known", issue_key="rust")
        case = HealthCase.objects.get()
        self.client.post(reverse("health_case_frequency", args=[case.pk]), {"check_every_days": "3"})
        case.refresh_from_db()
        self.assertEqual((case.check_every_days, case.next_check_date), (3, self.today + timedelta(days=3)))
        self.assertEqual(CareTask.objects.get(kind="health", completed_at__isnull=True).repeat_every_days, 3)

    def test_due_updates_are_listed(self):
        self.post_check(action="known", issue_key="rust")
        HealthCase.objects.update(next_check_date=self.today - timedelta(days=1))
        response = self.client.get(reverse("plant_health"))
        self.assertEqual(response.context["stats"]["due"], 1)
        self.assertContains(response, "Time for a photo update")

    def test_delete_after_analysed_photo_update(self):
        # Runs the real photo encoding (only the API call is faked): the earlier
        # photo must be closed again, or Windows refuses to delete it.
        import json
        from types import SimpleNamespace
        from unittest import mock
        self.post_check(action="known", issue_key="aphids")
        case = HealthCase.objects.get()
        reply = SimpleNamespace(stop_reason="end_turn", content=[
            SimpleNamespace(type="text", text=json.dumps({**AI_APHIDS, "progress": "better"}))])
        client = mock.MagicMock()
        client.beta.messages.create.return_value = reply
        with mock.patch("anthropic.Anthropic", return_value=client):
            self.client.post(reverse("health_case_update", args=[case.pk]),
                             {"image": _png("week2.png"), "analyse": "on"})
        images = [c.image for c in case.checks.all()]
        self.assertEqual(len(images), 2)
        response = self.client.post(reverse("health_case_delete", args=[case.pk]))
        self.assertRedirects(response, reverse("plant_health"))
        for image in images:
            self.assertFalse(image.storage.exists(image.name))

    def test_delete_survives_a_locked_photo(self):
        from unittest import mock
        self.post_check(action="known", issue_key="rust")
        case = HealthCase.objects.get()
        with mock.patch("django.core.files.storage.FileSystemStorage.delete",
                        side_effect=PermissionError("[WinError 32] in use")):
            response = self.client.post(reverse("health_case_delete", args=[case.pk]))
        self.assertRedirects(response, reverse("plant_health"))
        self.assertFalse(HealthCase.objects.exists())

    def test_delete_removes_case_photos_and_reminder(self):
        self.post_check(action="known", issue_key="rust")
        case = HealthCase.objects.get()
        image = case.checks.get().image
        self.assertTrue(image.storage.exists(image.name))
        self.client.post(reverse("health_case_delete", args=[case.pk]))
        self.assertFalse(HealthCase.objects.exists())
        self.assertFalse(image.storage.exists(image.name))
        self.assertFalse(CareTask.objects.filter(kind="health").exists())

    def test_other_users_cannot_see_or_change_cases(self):
        self.post_check(action="known", issue_key="rust")
        case = HealthCase.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("health_case", args=[case.pk])).status_code, 404)
        for name in ("health_case_update", "health_case_issue", "health_case_reanalyse",
                     "health_case_resolve", "health_case_frequency", "health_case_delete"):
            with self.subTest(action=name):
                self.assertEqual(self.client.post(reverse(name, args=[case.pk])).status_code, 404)
        response = self.client.post(reverse("health_check_new"), {
            "plant": self.plant.pk, "image": _png(), "action": "known", "issue_key": "rust",
            "severity": "mild", "check_every_days": "7",
        })
        self.assertIn("plant", response.context["form"].errors)
        self.assertEqual(HealthCase.objects.count(), 1)

    def test_rejects_non_image_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        response = self.post_check(action="known", issue_key="rust",
                                   image=SimpleUploadedFile("x.png", b"not an image", content_type="image/png"))
        self.assertIn("image", response.context["form"].errors)


class HealthAITests(TestCase):
    """The request sent to Claude and how its reply is handled (no network)."""

    def setUp(self):
        self.plant = Plant(name="Rosie", check_interval_days=7)

    def fake_client(self, *, stop_reason="end_turn", text=None):
        import json
        from types import SimpleNamespace
        from unittest import mock
        reply = SimpleNamespace(
            stop_reason=stop_reason,
            content=[SimpleNamespace(type="text", text=text if text is not None else json.dumps(AI_APHIDS))],
        )
        client = mock.MagicMock()
        client.beta.messages.create.return_value = reply
        patcher = mock.patch("anthropic.Anthropic", return_value=client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return client

    def test_sends_photo_with_structured_output(self):
        from . import health_ai
        client = self.fake_client()
        result = health_ai.analyse(_png(), plant=self.plant, notes="Sticky", previous_image=_png(),
                                   previous_title="Aphids")
        self.assertEqual(result["issues"][0]["key"], "aphids")
        kwargs = client.beta.messages.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5-5")
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")
        content = kwargs["messages"][0]["content"]
        images = [b for b in content if b["type"] == "image"]
        self.assertEqual(len(images), 2)  # earlier + latest photo
        self.assertEqual(images[0]["source"]["media_type"], "image/jpeg")
        self.assertIn("Sticky", content[-1]["text"])
        self.assertIn("Aphids", content[-1]["text"])

    def test_refusal_and_bad_replies_raise_readable_errors(self):
        from . import health_ai
        for stop_reason, text in (("refusal", ""), ("max_tokens", "{"), ("end_turn", "{not json")):
            with self.subTest(stop_reason=stop_reason):
                self.fake_client(stop_reason=stop_reason, text=text)
                with self.assertRaises(health_ai.AnalysisError):
                    health_ai.analyse(_png(), plant=self.plant)

    def test_not_a_plant(self):
        import json
        from . import health_ai
        self.fake_client(text=json.dumps({**AI_HEALTHY, "is_plant": False}))
        with self.assertRaisesMessage(health_ai.AnalysisError, "doesn't look like a plant"):
            health_ai.analyse(_png(), plant=self.plant)

    def test_missing_credentials_is_a_readable_error(self):
        import os
        from unittest import mock
        from . import health_ai
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesMessage(health_ai.AnalysisError, "no Anthropic API key"):
                health_ai.analyse(_png(), plant=self.plant)
