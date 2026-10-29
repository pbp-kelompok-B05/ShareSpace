import re
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import redirect, render, resolve_url
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import include, path, reverse

from authentication import urls as auth_urls
from ShareSpace.views import landing_page


def _base_page(request):
    return render(request, "base.html")


def _message_page(request):
    messages.success(request, "Barang berhasil disimpan.")
    messages.error(request, "Gagal menghapus barang.")
    messages.info(request, "<script>alert(1)</script>")
    return render(request, "base.html")


def _forbidden_with_message(request):
    raise PermissionDenied("Hanya pemilik barang yang dapat mengubah barang ini.")


def _forbidden_plain(request):
    raise PermissionDenied


def _message_then_login(request):
    messages.success(request, "Pesan menuju login.")
    return redirect("authentication:login")


def _message_then_profile(request):
    messages.success(request, "Pesan menuju profil.")
    return redirect("authentication:profile")


# Urlconf khusus test: URL modul tiruan agar link navbar yang bergantung pada
# {% url ... as var %} bisa diuji walau app modul lain belum ada di branch ini.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", landing_page, name="landing_page"),
    # URL asli authentication ditambah halaman profil tiruan (view profil belum ada).
    path("auth/", include((
        auth_urls.urlpatterns + [path("profile/", _base_page, name="profile")],
        "authentication",
    ))),
    path("items/", include(([
        path("", _base_page, name="catalog"),
        path("mine/", _base_page, name="my_items"),
    ], "items"))),
    path("loans/", include(([path("", _base_page, name="list")], "loans"))),
    path("cod/", include(([path("", _base_page, name="location_list")], "cod_location"))),
    path("reports/", include(([
        path("", _base_page, name="report_list"),
        path("mine/", _base_page, name="my_reports"),
    ], "review"))),
    path("_test/messages/", _message_page),
    path("_test/messages-login/", _message_then_login),
    path("_test/messages-profile/", _message_then_profile),
    path("_test/forbidden/", _forbidden_with_message),
    path("_test/forbidden-plain/", _forbidden_plain),
]

class MinimalUrlconf:
    """Urlconf tanpa URL modul mana pun, untuk menguji navbar saat modul belum ter-merge.

    Berupa class (bukan modul) karena urlconf cukup objek hashable yang punya urlpatterns.
    """

    urlpatterns = [
        path("", landing_page, name="landing_page"),
        path("auth/", include((auth_urls.urlpatterns, "authentication"))),
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


class BrandFigmaTest(TestCase):
    """Logo, tagline footer, dan hak cipta mengikuti mockup design system di Figma."""

    def setUp(self):
        self.html = self.client.get(reverse("landing_page")).content.decode()

    def test_logo_in_header_and_footer(self):
        # Logo Figma: kotak hijau "SS" + teks "ShareSpace"; kotak hanya dekorasi.
        self.assertEqual(self.html.count('<span class="brand-logo" aria-hidden="true">SS</span>'), 2)
        self.assertEqual(self.html.count('<span class="brand-name">ShareSpace</span>'), 2)
        self.assertEqual(self.html.count('aria-label="ShareSpace, kembali ke beranda"'), 2)
        self.assertNotIn("brand-dot", self.html)

    def test_footer_tagline_and_copyright(self):
        footer = re.search(r'<footer class="site-footer">(.*?)</footer>', self.html, re.S).group(1)
        self.assertIn("Community Lending Library", footer)
        self.assertIn(f"© {date.today().year} ShareSpace", footer)
        self.assertIn("Proyek kelompok PBP B05", footer)

    def test_brand_styles_defined(self):
        with open(finders.find("css/style.css"), encoding="utf-8") as f:
            css = f.read()
        for selector in (".brand-logo", ".brand-name", ".badge-new"):
            with self.subTest(selector=selector):
                self.assertIn(selector, css)


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

    def test_anonymous_sees_login_and_start_button(self):
        html = self.client.get(reverse("landing_page")).content.decode()
        self.assertIn(f'href="{reverse("authentication:login")}"', html)
        # Katalog sudah ada di urlconf proyek: tombol "Mulai jelajahi" mengarah ke katalog.
        self.assertRegex(
            html,
            r'<a class="button button-primary button-sm header-start" href="%s">\s*Mulai jelajahi'
            % re.escape(reverse("items:catalog")),
        )
        self.assertNotIn(reverse("authentication:logout"), html)

    def test_authenticated_does_not_see_start_button(self):
        self.client.login(username="warga_nav", password=self.password)
        self.assertNotContains(self.client.get(reverse("landing_page")), "Mulai jelajahi")

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

    @override_settings(ROOT_URLCONF=MinimalUrlconf)
    def test_module_links_hidden_when_urls_missing(self):
        # Tanpa URL modul, {% url ... as var %} kosong: halaman tetap render dan link modul tidak tampil.
        response = self.client.get(reverse("authentication:login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Katalog Komunitas")
        self.assertNotContains(response, "Lokasi COD")

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

    def test_profile_link_hidden_for_anonymous(self):
        response = self.client.get("/")
        self.assertNotContains(response, 'href="/auth/profile/"')

    def test_profile_link_is_first_in_user_menu(self):
        self.client.login(username="warga_mod", password=self.password)
        html = self.client.get("/").content.decode()
        self.assertRegex(
            html,
            r'<div class="user-menu-panel">\s*<a href="/auth/profile/">Profil saya</a>\s*<a href="/items/mine/"',
        )

    def test_profile_link_marked_active_on_profile_page(self):
        self.client.login(username="warga_mod", password=self.password)
        html = self.client.get("/auth/profile/").content.decode()
        self.assertRegex(html, r'<a href="/auth/profile/" aria-current="page">Profil saya</a>')

    def test_report_link_only_for_staff(self):
        self.client.login(username="admin_mod", password=self.password)
        self.assertContains(self.client.get("/"), 'href="/reports/"')

    def test_my_reports_link_after_loans_for_authenticated(self):
        self.client.login(username="warga_mod", password=self.password)
        html = self.client.get("/").content.decode()
        self.assertRegex(
            html,
            r'<a href="/loans/">Peminjaman saya</a>\s*<a href="/reports/mine/">Laporan saya</a>',
        )

    def test_my_reports_link_hidden_for_anonymous(self):
        response = self.client.get("/")
        self.assertNotContains(response, 'href="/reports/mine/"')
        self.assertNotContains(response, "Laporan saya")

    def test_my_reports_link_marked_active_on_its_page(self):
        self.client.login(username="warga_mod", password=self.password)
        html = self.client.get("/reports/mine/").content.decode()
        self.assertRegex(html, r'<a href="/reports/mine/" aria-current="page">Laporan saya</a>')
        self.assertNotRegex(html, r'<a href="/loans/" aria-current="page">')

    def test_staff_sees_my_reports_and_moderation_links(self):
        self.client.login(username="admin_mod", password=self.password)
        html = self.client.get("/").content.decode()
        self.assertIn('<a href="/reports/mine/">Laporan saya</a>', html)
        self.assertIn('<a href="/reports/">Laporan</a>', html)

    def test_catalog_link_labelled_with_new_badge(self):
        html = self.client.get("/").content.decode()
        self.assertRegex(
            html,
            r'(?s)<nav class="main-nav"[^>]*>.*?<a href="/items/"[^>]*>Katalog Komunitas\s*<span class="badge badge-new">Baru</span></a>',
        )

    def test_start_button_points_to_catalog_when_available(self):
        html = self.client.get("/").content.decode()
        self.assertRegex(html, r'<a class="button button-primary button-sm header-start" href="/items/">\s*Mulai jelajahi')
        self.assertNotIn(f'href="{reverse("authentication:register")}"', html)

    def test_active_link_marked_with_aria_current(self):
        html = self.client.get("/items/").content.decode()
        self.assertRegex(html, r'<a[^>]*href="/items/"[^>]*aria-current="page"')
        self.assertNotRegex(html, r'<a[^>]*href="/cod/"[^>]*aria-current="page"')


class LoginUrlSettingTest(TestCase):
    """Standar kelompok: @login_required mengarah ke halaman login modul authentication."""

    def test_login_url_points_to_authentication_login(self):
        self.assertEqual(settings.LOGIN_URL, "authentication:login")
        self.assertEqual(resolve_url(settings.LOGIN_URL), reverse("authentication:login"))


@override_settings(ROOT_URLCONF=__name__)
class MessagesToastTest(TestCase):
    """Django messages dirender sebagai toast di base.html, tidak ganda di halaman auth, dan di-escape."""

    def test_toast_region_present_on_every_page(self):
        for url in ("/", "/auth/login/", "/auth/register/"):
            with self.subTest(url=url):
                self.assertRegex(
                    self.client.get(url).content.decode(),
                    r'<div[^>]*id="toast-region"[^>]*aria-live="polite"',
                )

    def test_messages_rendered_as_toasts_with_level(self):
        response = self.client.get("/_test/messages/")
        self.assertTemplateUsed(response, "partials/messages.html")
        html = response.content.decode()
        self.assertRegex(html, r'class="toast toast-success"[^>]*data-toast')
        self.assertRegex(html, r'class="toast toast-error"[^>]*data-toast')
        self.assertEqual(html.count("Barang berhasil disimpan."), 1)
        self.assertIn('aria-label="Tutup notifikasi"', html)

    def test_message_content_is_escaped(self):
        html = self.client.get("/_test/messages/").content.decode()
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_auth_pages_show_message_once(self):
        # login.html/register.html merender messages sendiri; base tidak boleh merender ulang.
        response = self.client.get("/_test/messages-login/", follow=True)
        html = response.content.decode()
        self.assertEqual(html.count("Pesan menuju login."), 1)
        self.assertNotIn('class="toast ', html)

    def test_register_success_message_shown_once(self):
        response = self.client.post(
            reverse("authentication:register"),
            {"username": "warga_baru", "password1": "PasswordUji123!", "password2": "PasswordUji123!"},
            follow=True,
        )
        self.assertEqual(response.content.decode().count("Akun berhasil dibuat"), 1)

    def test_other_auth_pages_show_message_as_toast(self):
        # Halaman authentication selain login/register (mis. profil) tidak merender messages sendiri.
        User.objects.create_user(username="warga_toast", password="PasswordUji123!")
        self.client.login(username="warga_toast", password="PasswordUji123!")
        response = self.client.get("/_test/messages-profile/", follow=True)
        self.assertEqual(response.resolver_match.view_name, "authentication:profile")
        html = response.content.decode()
        self.assertEqual(html.count("Pesan menuju profil."), 1)
        self.assertRegex(html, r'class="toast toast-success"[^>]*data-toast')

    def test_message_not_carried_over_from_auth_page(self):
        # Pesan yang sudah tampil di profil tidak boleh muncul lagi di halaman berikutnya.
        User.objects.create_user(username="warga_toast", password="PasswordUji123!")
        self.client.login(username="warga_toast", password="PasswordUji123!")
        self.client.get("/_test/messages-profile/", follow=True)
        self.assertNotContains(self.client.get("/"), "Pesan menuju profil.")

    def test_toast_script_loaded_and_avoids_innerhtml(self):
        self.assertRegex(self.client.get("/").content.decode(), r'<script defer src="[^"]*js/toast\.js"')
        path = finders.find("js/toast.js")
        self.assertIsNotNone(path)
        with open(path, encoding="utf-8") as f:
            script = f.read()
        # Teks toast dari server/HTMX harus lewat textContent agar tidak bisa menyisipkan HTML.
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)
        self.assertIn("htmx:responseError", script)
        self.assertIn("showToast", script)


class NotFoundPageTest(TestCase):
    """404 bersama dirender handler bawaan Django (DEBUG=False saat test) dengan base template."""

    def test_unknown_url_uses_shared_404_template(self):
        response = self.client.get("/halaman-yang-tidak-ada/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "Halaman tidak ditemukan", status_code=404)
        self.assertContains(response, f'href="{reverse("landing_page")}"', status_code=404)

    def test_404_title(self):
        response = self.client.get("/halaman-yang-tidak-ada/")
        self.assertContains(response, "<title>Halaman tidak ditemukan — ShareSpace</title>", status_code=404)


@override_settings(ROOT_URLCONF=__name__)
class ForbiddenPageTest(TestCase):
    """403 bersama: menampilkan pesan dari PermissionDenied dan ajakan login bila belum masuk."""

    def test_permission_denied_message_shown(self):
        response = self.client.get("/_test/forbidden/")
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "Hanya pemilik barang yang dapat mengubah barang ini.", status_code=403)

    def test_default_message_when_exception_empty(self):
        response = self.client.get("/_test/forbidden-plain/")
        self.assertContains(response, "Kamu tidak punya izin untuk membuka halaman ini.", status_code=403)

    def test_anonymous_gets_login_link_with_next(self):
        response = self.client.get("/_test/forbidden/")
        self.assertContains(response, 'href="/auth/login/?next=/_test/forbidden/"', status_code=403)

    def test_authenticated_does_not_get_login_link(self):
        User.objects.create_user(username="warga_403", password="PasswordUji123!")
        self.client.login(username="warga_403", password="PasswordUji123!")
        response = self.client.get("/_test/forbidden/")
        self.assertNotContains(response, "?next=", status_code=403)


class _SampleItemForm(forms.Form):
    name = forms.CharField(label="Nama barang", min_length=3, help_text="Minimal 3 karakter.")
    notes = forms.CharField(label="Catatan", required=False, widget=forms.Textarea)


class PaginationPartialTest(TestCase):
    """partials/pagination.html: query filter tetap terbawa, status halaman aksesibel, opsi HTMX."""

    def render(self, page_number, query="q=raket&category=Olahraga", **extra):
        request = RequestFactory().get(f"/items/?{query}&page={page_number}")
        page_obj = Paginator(range(100), 10).page(page_number)
        return render_to_string("partials/pagination.html", {"page_obj": page_obj, **extra}, request=request)

    def test_links_keep_filters_and_replace_page(self):
        html = self.render(5)
        self.assertIn('href="?q=raket&amp;category=Olahraga&amp;page=6"', html)
        self.assertIn('href="?q=raket&amp;category=Olahraga&amp;page=4"', html)
        self.assertNotIn("page=5&amp;page", html)

    def test_current_page_marked_and_landmark_labelled(self):
        html = self.render(5)
        self.assertIn('<nav class="pagination" aria-label="Navigasi halaman">', html)
        self.assertRegex(html, r'aria-current="page"[^>]*>\s*5\s*<')

    def test_far_pages_elided(self):
        html = self.render(5)
        self.assertIn("page=1", html)
        self.assertIn("page=10", html)
        self.assertNotIn("page=8", html)
        self.assertIn("…", html)

    def test_previous_disabled_on_first_page(self):
        html = self.render(1)
        self.assertRegex(html, r'<span[^>]*aria-disabled="true"[^>]*>.*?Sebelumnya</span>')
        self.assertNotIn('rel="prev"', html)
        self.assertIn('rel="next"', html)

    def test_htmx_attributes_when_target_given(self):
        html = self.render(2, hx_target="#item-list")
        self.assertIn('hx-get="?q=raket&amp;category=Olahraga&amp;page=3"', html)
        self.assertIn('hx-target="#item-list"', html)
        self.assertIn('hx-push-url="true"', html)

    def test_next_label_follows_figma(self):
        html = self.render(5)
        self.assertRegex(html, r'(?s)rel="next"[^>]*>.*?Selanjutnya</span>')
        self.assertNotIn("Berikutnya", html)

    def test_summary_shown_when_item_label_given(self):
        html = self.render(5, item_label="barang")
        self.assertRegex(html, r'<p class="pagination-summary">\s*Menampilkan 41–50 dari 100 barang\s*</p>')
        # Ringkasan di dalam landmark nav, sebelum tombol halaman (urutan baca kiri ke kanan seperti Figma).
        self.assertLess(html.find("pagination-summary"), html.find('class="pagination-controls"'))

    def test_summary_on_last_partial_page(self):
        request = RequestFactory().get("/items/?page=3")
        page_obj = Paginator(range(25), 10).page(3)
        html = render_to_string("partials/pagination.html", {"page_obj": page_obj, "item_label": "barang"}, request=request)
        self.assertIn("Menampilkan 21–25 dari 25 barang", html)

    def test_no_summary_without_item_label(self):
        self.assertNotIn("pagination-summary", self.render(5))

    def test_renders_nothing_for_single_page(self):
        request = RequestFactory().get("/items/")
        page_obj = Paginator(range(5), 10).page(1)
        html = render_to_string("partials/pagination.html", {"page_obj": page_obj}, request=request)
        self.assertEqual(html.strip(), "")


class FormFieldPartialTest(TestCase):
    """partials/form_field.html: label, help text, dan error terhubung lewat id yang dipakai aria-describedby Django."""

    def test_valid_field_has_label_and_help(self):
        form = _SampleItemForm()
        html = render_to_string("partials/form_field.html", {"field": form["name"]})
        self.assertIn('<label class="form-label" for="id_name">', html)
        self.assertIn('id="id_name_helptext"', html)
        self.assertIn('class="form-required" aria-hidden="true"', html)
        self.assertIn(" required ", html)  # atribut required pada input diumumkan pembaca layar
        self.assertNotIn("has-error", html)

    def test_invalid_field_shows_errors_with_matching_id(self):
        form = _SampleItemForm(data={"name": "ab"})
        form.is_valid()
        html = render_to_string("partials/form_field.html", {"field": form["name"]})
        self.assertIn("form-field has-error", html)
        self.assertIn('aria-invalid="true"', html)
        # Isi pesan mengikuti LANGUAGE_CODE; cukup pastikan pesan validasi ada di dalam elemen ber-id error.
        self.assertRegex(html, r'id="id_name_error"[^>]*>\s*<p[^>]*>[^<]*3')

    def test_optional_field_has_no_required_marker(self):
        html = render_to_string("partials/form_field.html", {"field": _SampleItemForm()["notes"]})
        self.assertNotIn("form-required", html)


class EmptyStatePartialTest(TestCase):
    """partials/empty_state.html: judul, teks, dan aksi opsional."""

    def test_with_action(self):
        html = render_to_string("partials/empty_state.html", {
            "title": "Belum ada barang", "text": "Tambahkan barang pertamamu.",
            "action_url": "/items/new/", "action_label": "Tambah barang",
        })
        self.assertIn('class="empty-state"', html)
        self.assertIn("<h2", html)
        self.assertIn("Belum ada barang", html)
        self.assertIn('href="/items/new/"', html)

    def test_without_action_and_escaped(self):
        html = render_to_string("partials/empty_state.html", {"title": "<b>Kosong</b>"})
        self.assertIn("&lt;b&gt;Kosong&lt;/b&gt;", html)
        self.assertNotIn("<a ", html)


class DesignTokensTest(TestCase):
    """Fokus terlihat (kontras cukup) dan prefers-reduced-motion berlaku global."""

    def test_focus_token_and_reduced_motion(self):
        with open(finders.find("css/style.css"), encoding="utf-8") as f:
            css = f.read().replace(" ", "")
        self.assertIn("--focus:", css)
        self.assertIn("a:focus-visible{outline-color:var(--focus)}", css)
        self.assertIn("transition-duration:.01ms!important", css)
        for component in (".button-secondary", ".button-danger", ".card", ".badge", ".form-input", ".empty-state", ".pagination"):
            with self.subTest(component=component):
                self.assertIn(component, css)


class FigmaComponentVariantsTest(TestCase):
    """Varian badge, chip, dan button dari sheet komponen Figma; warnanya lewat token agar ikut dark mode."""

    STATUS = ("pending", "approved", "active", "done", "rejected", "cancelled")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(finders.find("css/style.css"), encoding="utf-8") as f:
            css = re.sub(r"/\*.*?\*/", "", f.read(), flags=re.S)
        # Pasangan (daftar selector, deklarasi); rule di dalam @media ikut terbaca sebagai rule biasa.
        cls.rules = [
            ([s.strip() for s in selectors.split(",")], body.replace(" ", ""))
            for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)
        ]

    def decl(self, selector):
        """Gabungan deklarasi semua rule yang selector-nya persis `selector`."""
        return ";".join(body for selectors, body in self.rules if selector in selectors)

    def test_availability_badges_are_solid(self):
        # Figma: "Tersedia" hijau solid, "Sedang Dipinjam" amber solid.
        available = self.decl(".badge-available")
        self.assertIn("background:var(--green)", available)
        self.assertIn("color:var(--on-primary)", available)
        self.assertIn("background:var(--amber)", self.decl(".badge-unavailable"))
        self.assertIn("color:var(--on-amber)", self.decl(".badge-unavailable"))

    def test_category_badge_is_outlined(self):
        category = self.decl(".badge-category")
        self.assertIn("background:var(--surface)", category)
        self.assertIn("border-color:var(--line)", category)

    def test_status_badges_defined_with_tokens(self):
        self.assertIn("content:", self.decl(".badge-status::before"))  # titik warna di depan label
        for status in self.STATUS:
            with self.subTest(status=status):
                body = self.decl(f".badge-status-{status}")
                self.assertIn("background:var(--", body)
                self.assertNotIn("#", body)

    def test_new_status_tokens_have_dark_values(self):
        light, dark = self.decl(":root"), self.decl(".dark")
        for token in ("--info:", "--info-bg:", "--neutral:", "--neutral-bg:", "--slate:", "--slate-bg:"):
            with self.subTest(token=token):
                self.assertIn(token, light)
                self.assertIn(token, dark)
        self.assertIn("--amber:", light)
        self.assertIn("--on-amber:", light)

    def test_chip_states(self):
        self.assertTrue(self.decl(".chip"))
        for selector in ('.chip:has(input:checked)', '.chip[aria-pressed="true"]'):
            with self.subTest(selector=selector):
                self.assertIn("background:var(--green)", self.decl(selector))
        # Input radio/checkbox disembunyikan secara visual, jadi fokusnya ditampilkan di chip.
        self.assertIn("outline:3pxsolidvar(--focus)", self.decl(".chip:has(input:focus-visible)"))

    def test_form_input_radius_follows_figma(self):
        body = self.decl(".form-input")
        self.assertIn("border-radius:10px", body)
        self.assertNotIn("border-radius:8px", body)

    def test_pagination_summary_styles(self):
        self.assertIn("margin-right:auto", self.decl(".pagination-summary"))
        self.assertTrue(self.decl(".pagination-controls"))

    def test_danger_outline_button_added_without_replacing_solid(self):
        outline = self.decl(".button-danger-outline")
        self.assertIn("color:var(--danger)", outline)
        self.assertIn("background:var(--surface)", outline)
        self.assertIn("background:var(--danger)", self.decl(".button-danger"))
