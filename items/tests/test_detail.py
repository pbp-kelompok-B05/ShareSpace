from django.contrib.auth import get_user_model
from django.db import connection
from django.templatetags.static import static
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from items.models import Item
from items.serializers import serialize_item
from items.tests.test_models import ItemTestMixin

User = get_user_model()

# Teks tombol aksi; dipakai untuk memastikan tombol tidak tampil saat URL-nya belum ada.
ACTION_LABELS = ["Ajukan Peminjaman", "Masuk untuk meminjam", "Edit Barang", "Hapus Barang", "Laporkan barang"]


class DetailTestMixin(ItemTestMixin):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other = User.objects.create_user(username="itemtest_detail_other")
        cls.staff = User.objects.create_user(username="itemtest_detail_staff", is_staff=True)

    def detail_url(self, item):
        return reverse("items:detail", args=[item.pk])

    def get_detail(self, item, user=None):
        if user is not None:
            self.client.force_login(user)
        return self.client.get(self.detail_url(item))

    def assertItemQueryJoinsOwner(self, url):
        """Barang dan pemilik diambil dalam satu query (select_related), tanpa query owner terpisah."""
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(url)
        item_queries = [q["sql"] for q in ctx.captured_queries if "items_item" in q["sql"]]
        user_queries = [q["sql"] for q in ctx.captured_queries if "auth_user" in q["sql"]]
        self.assertEqual(len(item_queries), 1)
        self.assertIn("auth_user", item_queries[0])
        self.assertEqual(user_queries, item_queries)


class ItemDetailPageTest(DetailTestMixin, TestCase):
    """Halaman detail barang: terbuka untuk tamu, menampilkan info barang dengan aman."""

    def test_url_is_under_katalog(self):
        item = self.make_item()
        self.assertEqual(self.detail_url(item), f"/katalog/{item.pk}/")

    def test_anonymous_can_open_detail(self):
        item = self.make_item()
        response = self.get_detail(item)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/detail.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertEqual(response.context["item"], item)

    def test_title_and_heading(self):
        response = self.get_detail(self.make_item())
        self.assertContains(response, "<title>Kipas Angin Meja — ShareSpace</title>", html=False)
        self.assertRegex(response.content.decode(), r"<h1[^>]*>\s*Kipas Angin Meja\s*</h1>")

    def test_shows_main_info(self):
        item = self.make_item(condition=Item.Condition.LIKE_NEW)
        response = self.get_detail(item)
        self.assertContains(response, "Elektronik")
        self.assertContains(response, "Seperti Baru")
        self.assertContains(response, item.description)
        self.assertContains(response, self.owner.username)
        self.assertContains(response, "Ditambahkan")

    def test_description_keeps_line_breaks_and_is_escaped(self):
        item = self.make_item(description="Baris pertama cukup panjang.\nBaris kedua <script>alert(1)</script>")
        response = self.get_detail(item)
        self.assertContains(response, "Baris pertama cukup panjang.<br>Baris kedua &lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_name_is_escaped(self):
        response = self.get_detail(self.make_item(name="<b>Kipas</b>"))
        self.assertContains(response, "&lt;b&gt;Kipas&lt;/b&gt;")
        self.assertNotContains(response, "<b>Kipas</b>")

    def test_available_status(self):
        response = self.get_detail(self.make_item())
        self.assertContains(response, 'class="badge badge-available"')
        self.assertNotContains(response, "badge-unavailable")

    def test_borrowed_status(self):
        response = self.get_detail(self.make_item(is_available=False))
        self.assertContains(response, 'class="badge badge-unavailable"')
        self.assertContains(response, "Sedang Dipinjam")

    def test_verified_badge_only_when_verified(self):
        self.assertNotContains(self.get_detail(self.make_item()), "Terverifikasi")
        self.assertContains(self.get_detail(self.make_item(is_verified=True)), "Terverifikasi")

    def test_uses_image_url_with_alt(self):
        response = self.get_detail(self.make_item(image_url="https://example.com/kipas.jpg"))
        self.assertRegex(
            response.content.decode(),
            r'<img[^>]*src="https://example.com/kipas.jpg"[^>]*alt="Kipas Angin Meja"',
        )

    def test_placeholder_when_no_image_url(self):
        response = self.get_detail(self.make_item(category=Item.Category.SPORTS))
        self.assertContains(response, f'src="{static("items/img/placeholders/sports.svg")}"')

    def test_breadcrumb_links_to_catalog_and_category(self):
        item = self.make_item(category=Item.Category.OUTDOOR)
        html = self.get_detail(item).content.decode()
        catalog_url = reverse("items:catalog")
        self.assertIn('<nav class="breadcrumb" aria-label="Breadcrumb">', html)
        self.assertIn(f'href="{catalog_url}"', html)
        self.assertIn(f'href="{catalog_url}?category=outdoor"', html)
        self.assertRegex(html, r'<span aria-current="page">\s*Kipas Angin Meja\s*</span>')

    def test_owner_fetched_with_item_in_one_query(self):
        self.assertItemQueryJoinsOwner(self.detail_url(self.make_item()))

    def test_post_not_allowed(self):
        response = self.client.post(self.detail_url(self.make_item()))
        self.assertEqual(response.status_code, 405)


class ItemDetailVisibilityTest(DetailTestMixin, TestCase):
    """Barang terhapus, milik user nonaktif, atau tidak ada menghasilkan 404, termasuk untuk admin."""

    def assertNotFoundForEveryone(self, url):
        for user in (None, self.owner, self.staff):
            with self.subTest(user=user):
                self.client.logout()
                if user is not None:
                    self.client.force_login(user)
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_soft_deleted_item_is_404(self):
        item = self.make_item()
        item.soft_delete()
        self.assertNotFoundForEveryone(self.detail_url(item))

    def test_item_of_inactive_owner_is_404(self):
        owner = User.objects.create_user(username="itemtest_detail_inactive", is_active=False)
        item = self.make_item(owner=owner)
        self.assertNotFoundForEveryone(self.detail_url(item))

    def test_unknown_pk_is_404(self):
        last = Item.all_objects.order_by("-pk").first()
        unknown_pk = (last.pk if last else 0) + 1000
        self.assertNotFoundForEveryone(reverse("items:detail", args=[unknown_pk]))

    def test_borrowed_item_still_visible(self):
        self.assertEqual(self.get_detail(self.make_item(is_available=False)).status_code, 200)


@override_settings(ROOT_URLCONF="items.tests.urls_with_actions")
class ItemDetailActionsTest(DetailTestMixin, TestCase):
    """Tombol aksi saat URL modul terkait sudah ada: edit/hapus untuk pemilik atau admin, pinjam dan lapor untuk user lain."""

    def hrefs(self, item):
        return {
            "edit": f'href="{reverse("items:edit", args=[item.pk])}"',
            "delete": f'href="{reverse("items:delete", args=[item.pk])}"',
            "loan": f'href="{reverse("loans:create", args=[item.pk])}"',
            "report": f'href="{reverse("review:report_item_create", args=[item.pk])}"',
            "login": f'href="{reverse("authentication:login")}?next={self.detail_url(item)}"',
        }

    def assertLinks(self, response, item, shown, hidden):
        hrefs = self.hrefs(item)
        for key in shown:
            with self.subTest(shown=key):
                self.assertContains(response, hrefs[key])
        for key in hidden:
            with self.subTest(hidden=key):
                self.assertNotContains(response, hrefs[key])

    def test_context_flags_manage_permission(self):
        item = self.make_item()
        self.assertTrue(self.get_detail(item, self.owner).context["can_manage"])
        self.client.logout()
        self.assertFalse(self.get_detail(item, self.other).context["can_manage"])

    def test_owner_sees_edit_and_delete_only(self):
        item = self.make_item()
        response = self.get_detail(item, self.owner)
        self.assertLinks(response, item, shown=["edit", "delete"], hidden=["loan", "report", "login"])
        self.assertContains(response, "Edit Barang")
        self.assertContains(response, "Hapus Barang")

    def test_staff_can_manage_and_borrow_other_users_item(self):
        item = self.make_item()
        response = self.get_detail(item, self.staff)
        self.assertLinks(response, item, shown=["edit", "delete", "loan", "report"], hidden=["login"])

    def test_other_user_can_borrow_and_report(self):
        item = self.make_item()
        response = self.get_detail(item, self.other)
        self.assertLinks(response, item, shown=["loan", "report"], hidden=["edit", "delete", "login"])
        self.assertContains(response, "Ajukan Peminjaman")
        self.assertContains(response, "Laporkan barang")

    def test_anonymous_gets_login_link_with_next(self):
        item = self.make_item()
        response = self.get_detail(item)
        self.assertLinks(response, item, shown=["login", "report"], hidden=["edit", "delete", "loan"])
        self.assertContains(response, "Masuk untuk meminjam")

    def test_borrowed_item_cannot_be_requested(self):
        item = self.make_item(is_available=False)
        for user in (None, self.other):
            with self.subTest(user=user):
                response = self.get_detail(item, user)
                self.assertLinks(response, item, shown=["report"], hidden=["loan", "login"])
                self.assertContains(response, "sedang dipinjam")

    def test_borrowed_item_cannot_be_edited_or_deleted(self):
        item = self.make_item(is_available=False)
        for user in (self.owner, self.staff):
            with self.subTest(user=user):
                response = self.get_detail(item, user)
                self.assertLinks(response, item, shown=[], hidden=["edit", "delete"])
                self.assertContains(response, "tidak dapat diubah atau dihapus")


@override_settings(ROOT_URLCONF="items.tests.urls_without_actions")
class ItemDetailWithoutActionUrlsTest(DetailTestMixin, TestCase):
    """Selama URL edit/hapus, pinjaman, dan laporan belum ada, halaman tetap tampil tanpa tombolnya."""

    def test_no_action_buttons_for_anyone(self):
        item = self.make_item()
        for user in (None, self.owner, self.other, self.staff):
            with self.subTest(user=user):
                self.client.logout()
                response = self.get_detail(item, user)
                self.assertEqual(response.status_code, 200)
                for label in ACTION_LABELS:
                    self.assertNotContains(response, label)


class ItemDetailJsonTest(DetailTestMixin, TestCase):
    """Endpoint JSON detail: format sama dengan satu barang di katalog JSON (dipakai Flutter)."""

    def json_url(self, item_or_pk):
        pk = getattr(item_or_pk, "pk", item_or_pk)
        return reverse("items:detail_json", args=[pk])

    def assertNotFoundJson(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"detail": "Barang tidak ditemukan."})

    def test_url_is_under_katalog(self):
        item = self.make_item()
        self.assertEqual(self.json_url(item), f"/katalog/{item.pk}/json/")

    def test_returns_serialized_item(self):
        item = self.make_item(is_verified=True, image_url="https://example.com/kipas.jpg")
        response = self.client.get(self.json_url(item))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        item = Item.objects.select_related("owner").get(pk=item.pk)
        self.assertEqual(response.json(), serialize_item(item, response.wsgi_request))

    def test_placeholder_image_is_absolute(self):
        item = self.make_item(category=Item.Category.BOOKS)
        data = self.client.get(self.json_url(item)).json()
        self.assertEqual(data["image"], f"http://testserver{static('items/img/placeholders/books.svg')}")

    def test_soft_deleted_item_is_404_json(self):
        item = self.make_item()
        item.soft_delete()
        self.assertNotFoundJson(self.json_url(item))

    def test_item_of_inactive_owner_is_404_json(self):
        owner = User.objects.create_user(username="itemtest_detail_json_inactive", is_active=False)
        self.assertNotFoundJson(self.json_url(self.make_item(owner=owner)))

    def test_unknown_pk_is_404_json(self):
        last = Item.all_objects.order_by("-pk").first()
        self.assertNotFoundJson(self.json_url((last.pk if last else 0) + 1000))

    def test_borrowed_item_still_returned(self):
        data = self.client.get(self.json_url(self.make_item(is_available=False))).json()
        self.assertFalse(data["is_available"])

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(self.json_url(self.make_item())).status_code, 405)

    def test_owner_fetched_with_item_in_one_query(self):
        self.assertItemQueryJoinsOwner(self.json_url(self.make_item()))

    def test_deleted_at_not_exposed(self):
        # Sanity check: data internal soft delete tidak ikut terkirim.
        data = self.client.get(self.json_url(self.make_item())).json()
        self.assertNotIn("is_deleted", data)
        self.assertNotIn("deleted_at", data)
