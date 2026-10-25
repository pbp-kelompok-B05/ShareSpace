import re

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.shortcuts import render, resolve_url
from django.test import Client, TestCase, override_settings
from django.urls import include, path, reverse

from ShareSpace.views import landing_page


def _base_page(request):
    return render(request, "base.html")


# Urlconf khusus test: URL modul tiruan agar link navbar yang bergantung pada
# {% url ... as var %} bisa diuji walau app modul lain belum ada di branch ini.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", landing_page, name="landing_page"),
    path("auth/", include("authentication.urls")),
    path("items/", include(([
        path("", _base_page, name="catalog"),
        path("mine/", _base_page, name="my_items"),
    ], "items"))),
    path("loans/", include(([path("", _base_page, name="loan_list")], "loans"))),
    path("cod/", include(([path("", _base_page, name="location_list")], "cod_location"))),
    path("reports/", include(([path("", _base_page, name="report_list")], "review"))),
]


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


class DarkModeTest(TestCase):
    """Dark mode berbasis class: init sinkron sebelum CSS, toggle aksesibel, token tersedia."""

    def setUp(self):
        self.html = self.client.get(reverse("landing_page")).content.decode()

    def _read_static(self, path):
        found = finders.find(path)
        self.assertIsNotNone(found, f"{path} tidak ditemukan")
        with open(found, encoding="utf-8") as f:
            return f.read()

    def test_theme_init_runs_synchronously_before_stylesheet(self):
        tag = re.search(r'<script[^>]*js/theme-init\.js[^>]*>', self.html)
        self.assertIsNotNone(tag)
        self.assertNotIn("defer", tag.group(0))
        self.assertNotIn("async", tag.group(0))
        self.assertLess(tag.start(), self.html.find("css/style.css"))

    def test_theme_script_deferred(self):
        self.assertRegex(self.html, r'<script defer src="[^"]*js/theme\.js"')

    def test_theme_toggle_button_accessible(self):
        tag = re.search(r"<button[^>]*data-theme-toggle[^>]*>", self.html)
        self.assertIsNotNone(tag)
        self.assertIn('type="button"', tag.group(0))
        self.assertIn('aria-pressed="false"', tag.group(0))
        self.assertIn('aria-label="Mode gelap"', tag.group(0))

    def test_theme_preference_storage_is_failsafe(self):
        for path in ("js/theme-init.js", "js/theme.js"):
            with self.subTest(path=path):
                script = self._read_static(path)
                self.assertIn("localStorage", script)
                self.assertIn("catch", script)

    def test_dark_tokens_defined(self):
        css = self._read_static("css/style.css")
        self.assertIn("--surface:", css)
        self.assertIn("--on-primary:", css)
        self.assertIn(".dark{", css.replace(" ", ""))
        config = self._read_static("js/tailwind.config.js")
        self.assertIn("surface: 'var(--surface)'", config)
        self.assertIn("'on-primary': 'var(--on-primary)'", config)


class NavbarTest(TestCase):
    """Navbar global: menu user, link admin, anchor landing, dan hamburger mobile."""

    def setUp(self):
        self.password = "PasswordUji123!"
        self.user = User.objects.create_user(username="warga_nav", password=self.password)
        self.staff = User.objects.create_user(username="admin_nav", password=self.password, is_staff=True)

    def test_anonymous_sees_login_and_register(self):
        response = self.client.get(reverse("landing_page"))
        self.assertContains(response, f'href="{reverse("authentication:login")}"')
        self.assertContains(response, f'href="{reverse("authentication:register")}"')
        self.assertNotContains(response, reverse("authentication:logout"))

    def test_authenticated_sees_user_menu_with_post_logout(self):
        self.client.login(username="warga_nav", password=self.password)
        html = self.client.get(reverse("landing_page")).content.decode()
        self.assertIn("warga_nav", html)
        form = re.search(
            r'<form[^>]*method="post"[^>]*action="%s"[^>]*>(.*?)</form>' % reverse("authentication:logout"),
            html, re.S,
        )
        self.assertIsNotNone(form)
        self.assertIn("csrfmiddlewaretoken", form.group(1))
        self.assertNotIn(f'href="{reverse("authentication:login")}"', html)

    def test_admin_link_only_for_staff(self):
        admin_url = reverse("admin:index")
        self.client.login(username="warga_nav", password=self.password)
        self.assertNotContains(self.client.get(reverse("landing_page")), f'href="{admin_url}"')
        self.client.login(username="admin_nav", password=self.password)
        self.assertContains(self.client.get(reverse("landing_page")), f'href="{admin_url}"')

    def test_landing_anchors_only_on_landing_page(self):
        anchor = f'href="{reverse("landing_page")}#cara-kerja"'
        self.assertContains(self.client.get(reverse("landing_page")), anchor)
        self.assertNotContains(self.client.get(reverse("authentication:login")), anchor)

    def test_module_links_hidden_when_urls_missing(self):
        # Urlconf proyek di branch ini belum punya URL modul; halaman tetap render tanpa error.
        response = self.client.get(reverse("authentication:login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, ">Katalog<")

    def test_mobile_menu_toggle_accessible(self):
        html = self.client.get(reverse("landing_page")).content.decode()
        tag = re.search(r"<button[^>]*data-nav-toggle[^>]*>", html)
        self.assertIsNotNone(tag)
        self.assertIn('aria-controls="site-menu"', tag.group(0))
        self.assertIn('aria-expanded="false"', tag.group(0))
        self.assertIn('aria-label="Buka menu navigasi"', tag.group(0))
        self.assertIn('id="site-menu"', html)
        self.assertRegex(html, r'<script defer src="[^"]*js/nav\.js"')


@override_settings(ROOT_URLCONF=__name__)
class NavbarModuleLinksTest(TestCase):
    """Link modul muncul begitu URL-nya ada; link pribadi hanya untuk user login."""

    def setUp(self):
        self.password = "PasswordUji123!"
        User.objects.create_user(username="warga_mod", password=self.password)
        User.objects.create_user(username="admin_mod", password=self.password, is_staff=True)

    def test_public_links_for_anonymous(self):
        response = self.client.get("/auth/login/")
        self.assertContains(response, 'href="/items/"')
        self.assertContains(response, 'href="/cod/"')
        self.assertNotContains(response, 'href="/items/mine/"')
        self.assertNotContains(response, 'href="/loans/"')

    def test_private_links_for_authenticated(self):
        self.client.login(username="warga_mod", password=self.password)
        response = self.client.get("/")
        self.assertContains(response, 'href="/items/mine/"')
        self.assertContains(response, 'href="/loans/"')
        self.assertNotContains(response, 'href="/reports/"')

    def test_report_link_only_for_staff(self):
        self.client.login(username="admin_mod", password=self.password)
        self.assertContains(self.client.get("/"), 'href="/reports/"')

    def test_active_link_marked_with_aria_current(self):
        html = self.client.get("/items/").content.decode()
        self.assertRegex(html, r'<a[^>]*href="/items/"[^>]*aria-current="page"')
        self.assertNotRegex(html, r'<a[^>]*href="/cod/"[^>]*aria-current="page"')


class LoginUrlSettingTest(TestCase):
    """Standar kelompok: @login_required mengarah ke halaman login modul authentication."""

    def test_login_url_points_to_authentication_login(self):
        self.assertEqual(settings.LOGIN_URL, "authentication:login")
        self.assertEqual(resolve_url(settings.LOGIN_URL), reverse("authentication:login"))
