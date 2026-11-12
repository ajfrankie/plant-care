import uuid

from django.test import Client, TestCase
from django.urls import reverse

from .forms import LoginForm
from .models import User
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
                url = reverse(name)
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
        pages = [pattern for pattern in urlpatterns if pattern.name not in ("logout", "login")]
        for pattern in pages:
            with self.subTest(page=pattern.name):
                self.assertEqual(self.client.get(reverse(pattern.name)).status_code, 200)

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
        plants = self.client.get(reverse("my_plants")).content.decode()
        library = self.client.get(reverse("library")).content.decode()
        self.assertIn(f'href="{reverse("plant_view")}"', plants)
        self.assertIn(f'href="{reverse("library_view")}"', library)
