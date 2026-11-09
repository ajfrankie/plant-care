from django.test import SimpleTestCase
from django.urls import reverse

from .urls import urlpatterns


class PageRenderingTests(SimpleTestCase):
    def test_every_page_renders(self):
        for pattern in urlpatterns:
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
