from django.test import TestCase
from django.urls import reverse


class BaseTemplateStructureTest(TestCase):
    """Base template dipecah ke partial dan tetap dipakai semua halaman yang ada."""

    PAGES = ("landing_page", "authentication:login", "authentication:register")

    def test_existing_pages_render_with_base_and_partials(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "base.html")
                self.assertTemplateUsed(response, "partials/header.html")
                self.assertTemplateUsed(response, "partials/footer.html")

    def test_skip_link_targets_main_content(self):
        response = self.client.get(reverse("landing_page"))
        self.assertContains(response, 'class="skip-link" href="#konten"')
        self.assertContains(response, '<main id="konten"')

    def test_header_and_footer_present(self):
        response = self.client.get(reverse("landing_page"))
        self.assertContains(response, 'class="site-header"')
        self.assertContains(response, 'class="site-footer"')
        self.assertContains(response, 'aria-label="Navigasi utama"')

    def test_footer_shows_group_name(self):
        response = self.client.get(reverse("landing_page"))
        self.assertContains(response, "Proyek kelompok PBP B05")
