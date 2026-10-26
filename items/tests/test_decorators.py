import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from items.decorators import item_owner_required, rate_limit
from items.models import Item
from items.tests.test_models import ItemTestMixin

User = get_user_model()

FORBIDDEN_MESSAGE = "Hanya pemilik barang atau admin yang dapat mengubah barang ini."
BORROWED_MESSAGE = "Barang sedang dipinjam sehingga tidak dapat diubah atau dihapus."
HTMX_HEADERS = {"HX-Request": "true"}

TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "items-decorator-tests",
    }
}


def toast_of(response):
    """Isi event showToast dari header HX-Trigger."""
    return json.loads(response["HX-Trigger"])["showToast"]


class ItemOwnerRequiredTest(ItemTestMixin, TestCase):
    """Decorator kepemilikan: login, 404 untuk barang tak terlihat, 403 untuk bukan pemilik/barang dipinjam."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other = User.objects.create_user(username="itemtest_deco_other")
        cls.staff = User.objects.create_user(username="itemtest_deco_staff", is_staff=True)

    def setUp(self):
        self.factory = RequestFactory()
        self.calls = []

        @item_owner_required
        def view(request, item):
            self.calls.append(item)
            return HttpResponse("ok")

        self.view = view

    def call(self, user, pk, htmx=False, method="get"):
        headers = HTMX_HEADERS if htmx else {}
        request = getattr(self.factory, method)(f"/katalog/{pk}/edit/", headers=headers)
        request.user = user
        return self.view(request, pk=pk)

    # --- Akses yang diizinkan ---

    def test_owner_gets_item_object(self):
        item = self.make_item()
        response = self.call(self.owner, item.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls, [item])
        self.assertIsInstance(self.calls[0], Item)

    def test_owner_allowed_for_post(self):
        item = self.make_item()
        response = self.call(self.owner, item.pk, method="post")
        self.assertEqual(response.status_code, 200)

    def test_staff_can_manage_other_users_item(self):
        item = self.make_item()
        response = self.call(self.staff, item.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls, [item])

    def test_item_and_owner_loaded_in_one_query(self):
        item = self.make_item()
        with self.assertNumQueries(1):
            self.call(self.owner, item.pk)
        # owner sudah ikut di-join (select_related), tanpa query tambahan.
        with self.assertNumQueries(0):
            self.assertEqual(self.calls[0].owner, self.owner)

    def test_wraps_preserves_view_name(self):
        @item_owner_required
        def edit_item(request, item):
            """Docstring view."""
        self.assertEqual(edit_item.__name__, "edit_item")
        self.assertEqual(edit_item.__doc__, "Docstring view.")

    # --- Tamu ---

    def test_anonymous_redirected_to_login(self):
        item = self.make_item()
        response = self.call(AnonymousUser(), item.pk)
        self.assertEqual(response.status_code, 302)
        login_url = reverse("authentication:login")
        self.assertTrue(response.url.startswith(login_url))
        self.assertIn(f"next=/katalog/{item.pk}/edit/", response.url.replace("%2F", "/"))
        self.assertEqual(self.calls, [])

    def test_anonymous_htmx_gets_hx_redirect(self):
        # Redirect 302 biasa akan diikuti HTMX dan halaman login masuk ke target swap.
        item = self.make_item()
        response = self.call(AnonymousUser(), item.pk, htmx=True)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(response["HX-Redirect"].startswith(reverse("authentication:login")))
        self.assertIn("next=", response["HX-Redirect"])
        self.assertEqual(self.calls, [])

    def test_anonymous_does_not_query_item(self):
        item = self.make_item()
        with self.assertNumQueries(0):
            self.call(AnonymousUser(), item.pk)

    # --- 404 ---

    def test_missing_item_is_404(self):
        missing_pk = (Item.all_objects.order_by("-pk").values_list("pk", flat=True).first() or 0) + 1
        with self.assertRaises(Http404):
            self.call(self.owner, missing_pk)
        self.assertEqual(self.calls, [])

    def test_soft_deleted_item_is_404(self):
        item = self.make_item()
        item.soft_delete()
        with self.assertRaises(Http404):
            self.call(self.owner, item.pk)

    def test_soft_deleted_item_is_404_for_staff(self):
        item = self.make_item()
        item.soft_delete()
        with self.assertRaises(Http404):
            self.call(self.staff, item.pk)

    def test_item_of_inactive_owner_is_404(self):
        inactive = User.objects.create_user(username="itemtest_deco_inactive", is_active=False)
        item = self.make_item(owner=inactive)
        with self.assertRaises(Http404):
            self.call(self.staff, item.pk)

    # --- 403 ---

    def test_other_user_forbidden_with_clear_message(self):
        item = self.make_item()
        with self.assertRaisesMessage(PermissionDenied, FORBIDDEN_MESSAGE):
            self.call(self.other, item.pk)
        self.assertEqual(self.calls, [])

    def test_other_user_forbidden_for_post(self):
        item = self.make_item()
        with self.assertRaisesMessage(PermissionDenied, FORBIDDEN_MESSAGE):
            self.call(self.other, item.pk, method="post")
        self.assertEqual(self.calls, [])

    def test_other_user_htmx_gets_403_with_toast(self):
        item = self.make_item()
        response = self.call(self.other, item.pk, htmx=True)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(toast_of(response), {"message": FORBIDDEN_MESSAGE, "level": "error"})
        self.assertEqual(self.calls, [])

    def test_borrowed_item_forbidden_for_owner(self):
        item = self.make_item(is_available=False)
        with self.assertRaisesMessage(PermissionDenied, BORROWED_MESSAGE):
            self.call(self.owner, item.pk)
        self.assertEqual(self.calls, [])

    def test_borrowed_item_forbidden_for_staff(self):
        item = self.make_item(is_available=False)
        with self.assertRaisesMessage(PermissionDenied, BORROWED_MESSAGE):
            self.call(self.staff, item.pk)

    def test_borrowed_item_htmx_gets_403_with_toast(self):
        item = self.make_item(is_available=False)
        response = self.call(self.owner, item.pk, htmx=True)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(toast_of(response)["message"], BORROWED_MESSAGE)

    def test_ownership_checked_before_borrowed_status(self):
        # User lain tidak perlu tahu status peminjaman barang orang lain.
        item = self.make_item(is_available=False)
        with self.assertRaisesMessage(PermissionDenied, FORBIDDEN_MESSAGE):
            self.call(self.other, item.pk)

    def test_403_page_renders_message_through_client(self):
        # Pastikan pesan sampai ke template 403 bersama lewat handler bawaan Django.
        item = self.make_item()
        self.client.force_login(self.other)
        with override_settings(ROOT_URLCONF="items.tests.urls_decorators"):
            response = self.client.get(f"/katalog/{item.pk}/edit/")
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")
        self.assertContains(response, FORBIDDEN_MESSAGE, status_code=403)


@override_settings(CACHES=TEST_CACHES)
class RateLimitTest(TestCase):
    """Rate limit per user per scope dengan cache Django; hanya POST yang dihitung."""

    LIMIT = 3
    PERIOD = 600

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="itemtest_rate_user")
        cls.other = User.objects.create_user(username="itemtest_rate_other")

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.calls = 0

        def view(request):
            self.calls += 1
            return HttpResponse("ok")

        self.raw_view = view
        self.view = rate_limit("test_scope", limit=self.LIMIT, period=self.PERIOD)(view)

    def call(self, user=None, method="post", htmx=False, view=None, ip="10.0.0.1"):
        headers = HTMX_HEADERS if htmx else {}
        request = getattr(self.factory, method)("/katalog/tambah/", headers=headers, REMOTE_ADDR=ip)
        request.user = user if user is not None else self.user
        return (view or self.view)(request)

    def exhaust(self, **kwargs):
        for _ in range(self.LIMIT):
            self.assertEqual(self.call(**kwargs).status_code, 200)

    def test_posts_within_limit_pass(self):
        self.exhaust()
        self.assertEqual(self.calls, self.LIMIT)

    def test_post_over_limit_returns_429_without_calling_view(self):
        self.exhaust()
        with self.assertTemplateUsed("items/rate_limited.html"):
            response = self.call()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.calls, self.LIMIT)
        self.assertContains(response, "Terlalu banyak permintaan", status_code=429)

    def test_429_has_retry_after_header(self):
        self.exhaust()
        response = self.call()
        retry_after = int(response["Retry-After"])
        self.assertGreater(retry_after, 0)
        self.assertLessEqual(retry_after, self.PERIOD)

    def test_htmx_over_limit_gets_toast(self):
        self.exhaust()
        response = self.call(htmx=True)
        self.assertEqual(response.status_code, 429)
        toast = toast_of(response)
        self.assertEqual(toast["level"], "error")
        self.assertIn("Terlalu banyak permintaan", toast["message"])
        self.assertIn("Retry-After", response)

    def test_get_is_not_counted(self):
        for _ in range(self.LIMIT * 3):
            self.assertEqual(self.call(method="get").status_code, 200)
        self.exhaust()

    def test_limit_is_per_user(self):
        self.exhaust()
        self.assertEqual(self.call(user=self.other).status_code, 200)

    def test_limit_is_per_scope(self):
        self.exhaust()
        other_scope = rate_limit("other_scope", limit=self.LIMIT, period=self.PERIOD)(self.raw_view)
        self.assertEqual(self.call(view=other_scope).status_code, 200)

    def test_anonymous_limited_per_ip(self):
        self.exhaust(user=AnonymousUser(), ip="10.0.0.9")
        self.assertEqual(self.call(user=AnonymousUser(), ip="10.0.0.9").status_code, 429)
        self.assertEqual(self.call(user=AnonymousUser(), ip="10.0.0.10").status_code, 200)

    def test_counter_resets_in_next_window(self):
        start = 1_000_000 * self.PERIOD
        with mock.patch("items.decorators.time") as fake_time:
            fake_time.time.return_value = start
            self.exhaust()
            self.assertEqual(self.call().status_code, 429)
            fake_time.time.return_value = start + self.PERIOD
            self.assertEqual(self.call().status_code, 200)

    def test_retry_after_counts_down_to_window_end(self):
        start = 1_000_000 * self.PERIOD
        with mock.patch("items.decorators.time") as fake_time:
            fake_time.time.return_value = start + 100
            self.exhaust()
            response = self.call()
        self.assertEqual(int(response["Retry-After"]), self.PERIOD - 100)

    def test_wraps_preserves_view_name(self):
        @rate_limit("x", limit=1, period=60)
        def create_item(request):
            """Docstring view."""
        self.assertEqual(create_item.__name__, "create_item")
        self.assertEqual(create_item.__doc__, "Docstring view.")
