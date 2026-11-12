import uuid
from datetime import date, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import LoginForm
from .models import Plant, PlantSpecies, User
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
        private = [p.name for p in urlpatterns if p.name not in self.public_pages + ["logout"]]
        self.assertIn("dashboard", private)
        for name in private:
            with self.subTest(page=name):
                url = reverse(name, args=[1] if name == "plant_edit" else None)
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
        args = {"plant_edit": [plant.pk]}
        pages = [pattern for pattern in urlpatterns if pattern.name not in ("logout", "login")]
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
        self.assertIn('placeholder="Search your plants..."', html)

    def test_search_box_hidden_when_page_has_no_search(self):
        html = self.client.get(reverse("plant_add")).content.decode()
        self.assertNotIn('data-field="search-box"', html)

    def test_my_plants_and_library_links_are_not_mixed_up(self):
        Plant.objects.create(
            created_user=self.user, name="Fern", planting_date=date(2026, 1, 1)
        )
        plants = self.client.get(reverse("my_plants")).content.decode()
        library = self.client.get(reverse("library")).content.decode()
        self.assertIn(f'href="{reverse("plant_view")}"', plants)
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
