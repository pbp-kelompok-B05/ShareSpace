import re

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import Client, TestCase
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


class BaseTemplateAssetsTest(TestCase):
    """Tailwind (Play CDN v3), HTMX, dan header CSRF global dimuat di base template."""

    TAILWIND_CDN = "https://cdn.tailwindcss.com/3.4.17"
    HTMX_CDN = "https://cdn.jsdelivr.net/npm/htmx.org@2.0.11/dist/htmx.min.js"

    def setUp(self):
        self.html = self.client.get(reverse("landing_page")).content.decode()

    def test_tailwind_cdn_pinned_and_config_loaded_after_it(self):
        cdn_pos = self.html.find(f'src="{self.TAILWIND_CDN}"')
        config_pos = self.html.find("js/tailwind.config.js")
        self.assertNotEqual(cdn_pos, -1)
        self.assertGreater(config_pos, cdn_pos)

    def test_tailwind_config_follows_group_standard(self):
        path = finders.find("js/tailwind.config.js")
        self.assertIsNotNone(path)
        with open(path, encoding="utf-8") as f:
            config = f.read()
        self.assertIn("darkMode: 'class'", config)
        self.assertIn("preflight: false", config)
        self.assertIn("container: false", config)

    def test_htmx_pinned_with_integrity(self):
        tag = re.search(r'<script[^>]*src="%s"[^>]*>' % re.escape(self.HTMX_CDN), self.html)
        self.assertIsNotNone(tag)
        self.assertIn('integrity="sha384-', tag.group(0))
        self.assertIn('crossorigin="anonymous"', tag.group(0))

    def test_body_sets_csrf_header_for_htmx(self):
        self.assertRegex(self.html, r"<body[^>]*hx-headers='\{\"X-CSRFToken\": \"[A-Za-z0-9]+\"\}'")


class GlobalCsrfHeaderTest(TestCase):
    """Token dari hx-headers benar-benar diterima CsrfViewMiddleware untuk request POST."""

    def test_post_with_token_from_hx_headers_passes_csrf(self):
        User.objects.create_user(username="tester_base", password="PasswordUji123!")
        client = Client(enforce_csrf_checks=True)
        client.login(username="tester_base", password="PasswordUji123!")
        html = client.get(reverse("landing_page")).content.decode()
        token = re.search(r'"X-CSRFToken": "([A-Za-z0-9]+)"', html).group(1)

        response = client.post(reverse("authentication:logout"), HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 302)

    def test_post_without_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("landing_page"))
        response = client.post(reverse("authentication:logout"))
        self.assertEqual(response.status_code, 403)
