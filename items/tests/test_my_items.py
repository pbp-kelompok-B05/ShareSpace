import re

from django.contrib.auth import get_user_model
from django.db import connection
from django.templatetags.static import static
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape

from items.forms import CatalogFilterForm
from items.models import Item
from items.tests.test_models import ItemTestMixin
from items.views import MY_ITEMS_PAGE_SIZE

User = get_user_model()

HTMX_HEADERS = {"HX-Request": "true"}


class MyItemsTestMixin(ItemTestMixin):
    """Owner test selalu user baru, jadi data seed tidak ikut muncul di "Barang saya"."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other = User.objects.create_user(username="itemtest_mine_other")
        cls.staff = User.objects.create_user(username="itemtest_mine_staff", is_staff=True)

    def setUp(self):
        self.url = reverse("items:my_items")

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def get(self, headers=None, **params):
        return self.client.get(self.url, params, headers=headers or {})

    def names(self, response):
        return [item.name for item in response.context["page_obj"].object_list]


class MyItemsAccessTest(MyItemsTestMixin, TestCase):
    """Halaman pribadi: wajib login, hanya GET."""

    def test_url(self):
        self.assertEqual(self.url, "/katalog/saya/")

    def test_anonymous_redirected_to_login(self):
        response = self.get()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("authentication:login")))
        self.assertIn("next=/katalog/saya/", response.url)

    def test_anonymous_htmx_gets_hx_redirect(self):
        response = self.get(headers=HTMX_HEADERS)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(response["HX-Redirect"].startswith(reverse("authentication:login")))

    def test_post_not_allowed(self):
        self.login()
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_logged_in_gets_full_page(self):
        self.login()
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/my_items.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertIsInstance(response.context["filter_form"], CatalogFilterForm)


class MyItemsContentTest(MyItemsTestMixin, TestCase):
    """Isi daftar: hanya barang milik sendiri, termasuk yang sedang dipinjam."""

    def setUp(self):
        super().setUp()
        self.login()

    def test_title_and_single_h1(self):
        response = self.get()
        self.assertContains(response, "<title>Barang Saya — ShareSpace</title>")
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, "Barang Saya")

    def test_lists_only_own_items(self):
        own = self.make_item(name="Bor Listrik Milikku")
        theirs = self.make_item(name="Bor Listrik Tetangga", owner=self.other)
        names = self.names(self.get())
        self.assertIn(own.name, names)
        self.assertNotIn(theirs.name, names)

    def test_staff_sees_only_own_items(self):
        self.make_item(name="Barang Pemilik Lain")
        own = self.make_item(name="Barang Admin", owner=self.staff)
        self.login(self.staff)
        self.assertEqual(self.names(self.get()), [own.name])

    def test_soft_deleted_item_hidden(self):
        item = self.make_item(name="Sudah Dihapus")
        item.soft_delete()
        self.assertNotIn(item.name, self.names(self.get()))

    def test_borrowed_item_shown_with_badge(self):
        item = self.make_item(name="Sedang Dipakai Tetangga", is_available=False)
        response = self.get()
        self.assertIn(item.name, self.names(response))
        self.assertContains(response, 'class="badge badge-unavailable"')

    def test_row_shows_main_info_and_links_to_detail(self):
        item = self.make_item(is_verified=True)
        response = self.get()
        self.assertContains(response, f'href="{reverse("items:detail", args=[item.pk])}"')
        self.assertContains(response, "Elektronik")
        self.assertContains(response, "Kondisi Baik")
        self.assertContains(response, "Terverifikasi")
        self.assertContains(response, 'class="badge badge-available"')

    def test_row_image_with_alt_or_placeholder(self):
        self.make_item(name="Raket", image_url="https://example.com/raket.jpg")
        self.make_item(name="Bola", category=Item.Category.SPORTS)
        html = self.get().content.decode()
        self.assertRegex(html, r'<img[^>]*src="https://example.com/raket.jpg"[^>]*alt="Raket"')
        self.assertIn(f'src="{static("items/img/placeholders/sports.svg")}"', html)

    def test_user_input_is_escaped(self):
        self.make_item(name="<script>alert(1)</script>")
        response = self.get()
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, escape("<script>alert(1)</script>"))

    def test_create_button(self):
        self.assertContains(self.get(), f'href="{reverse("items:create")}"')

    def test_header_link_marked_current(self):
        self.assertContains(self.get(), f'href="{self.url}" aria-current="page"')


class MyItemsStatsTest(MyItemsTestMixin, TestCase):
    """Ringkasan jumlah barang milik sendiri; tidak terpengaruh filter."""

    def setUp(self):
        super().setUp()
        self.login()
        self.make_item(name="Tersedia Satu")
        self.make_item(name="Tersedia Dua")
        self.make_item(name="Dipinjam", is_available=False)
        self.make_item(name="Dihapus").soft_delete()
        self.make_item(name="Milik Orang Lain", owner=self.other)

    def test_stats_in_context(self):
        stats = self.get().context["stats"]
        self.assertEqual(stats, {"total": 3, "available": 2, "borrowed": 1})

    def test_stats_ignore_filters(self):
        stats = self.get(q="dipinjam", available="1").context["stats"]
        self.assertEqual(stats["total"], 3)

    def test_stats_rendered(self):
        html = self.get().content.decode()
        self.assertRegex(html, r"Total barang</dt>\s*<dd[^>]*>3</dd>")
        self.assertRegex(html, r"Tersedia</dt>\s*<dd[^>]*>2</dd>")
        self.assertRegex(html, r"Sedang dipinjam</dt>\s*<dd[^>]*>1</dd>")


class MyItemsFilterTest(MyItemsTestMixin, TestCase):
    """Filter gabungan memakai CatalogFilterForm yang sama dengan katalog."""

    def setUp(self):
        super().setUp()
        self.login()
        self.camera = self.make_item(
            name="Kamera", category=Item.Category.ELECTRONICS, condition=Item.Condition.LIKE_NEW,
        )
        self.speaker = self.make_item(
            name="Speaker", category=Item.Category.ELECTRONICS, condition=Item.Condition.GOOD,
            is_available=False,
        )
        self.racket = self.make_item(
            name="Badminton", category=Item.Category.SPORTS, condition=Item.Condition.GOOD,
        )

    def test_filter_by_category(self):
        names = self.names(self.get(category=Item.Category.ELECTRONICS))
        self.assertCountEqual(names, [self.camera.name, self.speaker.name])

    def test_filter_by_condition(self):
        names = self.names(self.get(condition=Item.Condition.GOOD))
        self.assertCountEqual(names, [self.speaker.name, self.racket.name])

    def test_filter_available_only(self):
        names = self.names(self.get(available="1"))
        self.assertCountEqual(names, [self.camera.name, self.racket.name])

    def test_search(self):
        self.assertEqual(self.names(self.get(q="KAMERA")), [self.camera.name])

    def test_combined_filters(self):
        names = self.names(self.get(
            category=Item.Category.ELECTRONICS, condition=Item.Condition.GOOD,
        ))
        self.assertEqual(names, [self.speaker.name])

    def test_sort_by_name(self):
        self.assertEqual(
            self.names(self.get(sort="name")),
            [self.racket.name, self.camera.name, self.speaker.name],
        )

    def test_invalid_params_are_ignored(self):
        response = self.get(category="xyz", condition="rusak", sort="acak")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.names(response)), 3)

    def test_filter_form_uses_htmx_and_works_without_js(self):
        html = self.get().content.decode()
        form = re.search(r'<form[^>]*id="my-items-filter"[^>]*>', html)
        self.assertIsNotNone(form)
        form_tag = form.group(0)
        self.assertIn('method="get"', form_tag)
        self.assertIn(f'action="{self.url}"', form_tag)
        self.assertIn(f'hx-get="{self.url}"', form_tag)
        self.assertIn('hx-target="#my-item-list"', form_tag)
        self.assertIn('hx-push-url="true"', form_tag)
        self.assertIn('id="my-item-list"', html)

    def test_filter_controls_have_labels(self):
        response = self.get()
        for field in ["id_q", "id_category", "id_condition", "id_sort", "id_available"]:
            with self.subTest(field=field):
                self.assertContains(response, f'for="{field}"')
                self.assertContains(response, f'id="{field}"')

    def test_active_filters_are_kept_in_form(self):
        html = self.get(category=Item.Category.SPORTS, sort="oldest", available="1", q="bad").content.decode()
        self.assertRegex(html, r'<option value="sports" selected')
        self.assertRegex(html, r'<option value="oldest" selected')
        self.assertRegex(html, r'<input[^>]*name="available"[^>]*checked')
        self.assertIn('value="bad"', html)


class MyItemsPaginationTest(MyItemsTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.login()
        for i in range(MY_ITEMS_PAGE_SIZE + 1):
            self.make_item(name=f"Barang {i:02d}")

    def test_page_size_is_twenty(self):
        self.assertEqual(MY_ITEMS_PAGE_SIZE, 20)

    def test_first_page_is_full(self):
        response = self.get()
        self.assertEqual(len(self.names(response)), MY_ITEMS_PAGE_SIZE)
        self.assertEqual(response.context["page_obj"].paginator.count, MY_ITEMS_PAGE_SIZE + 1)

    def test_second_page_has_rest(self):
        self.assertEqual(len(self.names(self.get(page=2))), 1)

    def test_out_of_range_page_shows_last(self):
        self.assertEqual(self.get(page=999).context["page_obj"].number, 2)

    def test_pagination_keeps_filters_and_uses_htmx(self):
        html = self.get(category=Item.Category.ELECTRONICS).content.decode()
        links = re.findall(r'<a class="pagination-link"[^>]*href="([^"]*page=2[^"]*)"', html)
        self.assertTrue(links)
        self.assertIn("category=electronics", links[0])
        self.assertIn('hx-target="#my-item-list"', html)
        self.assertIn("Menampilkan 1–20 dari 21 barang", html)


class MyItemsHtmxTest(MyItemsTestMixin, TestCase):
    """Request HTMX mendapat partial; request biasa dan history restore mendapat halaman penuh."""

    def setUp(self):
        super().setUp()
        self.login()
        self.item = self.make_item(name="Tenda")

    def test_htmx_request_returns_partial(self):
        response = self.get(headers=HTMX_HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/partials/my_item_list.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, self.item.name)

    def test_history_restore_returns_full_page(self):
        response = self.get(headers={**HTMX_HEADERS, "HX-History-Restore-Request": "true"})
        self.assertTemplateUsed(response, "base.html")

    def test_response_varies_on_htmx_header(self):
        for headers in ({}, HTMX_HEADERS):
            with self.subTest(headers=headers):
                self.assertIn("HX-Request", self.get(headers=headers).headers.get("Vary", ""))


class MyItemsEmptyStateTest(MyItemsTestMixin, TestCase):
    """Dua empty state: belum punya barang sama sekali vs filter tidak menemukan apa pun."""

    def setUp(self):
        super().setUp()
        self.login()

    def assertNoItemsState(self, response):
        self.assertContains(response, "empty-state")
        self.assertContains(response, "Kamu belum punya barang")
        self.assertContains(response, f'class="button button-primary" href="{reverse("items:create")}"')
        self.assertNotContains(response, "Hapus semua filter")

    def test_no_items_without_filter(self):
        self.assertNoItemsState(self.get())

    def test_sort_alone_is_not_a_filter(self):
        self.assertNoItemsState(self.get(sort="name"))

    def test_no_items_htmx_partial(self):
        self.assertNoItemsState(self.get(headers=HTMX_HEADERS))

    def test_no_match_with_filter(self):
        self.make_item()
        response = self.get(q="tidakadazqx999")
        self.assertContains(response, "Tidak ada barang yang cocok")
        self.assertContains(response, f'href="{self.url}">Hapus semua filter')
        self.assertNotContains(response, "Kamu belum punya barang")

    def test_borrowed_filter_with_no_match(self):
        self.make_item(is_available=False)
        response = self.get(available="1")
        self.assertContains(response, "Tidak ada barang yang cocok")


class MyItemsQueryTest(MyItemsTestMixin, TestCase):
    """Jumlah query tetap, berapa pun banyaknya barang."""

    def count_queries(self, headers=None):
        with CaptureQueriesContext(connection) as ctx:
            self.get(headers=headers)
        return len(ctx.captured_queries)

    def test_query_count_constant(self):
        self.login()
        for headers in ({}, HTMX_HEADERS):
            with self.subTest(headers=headers):
                Item.objects.filter(owner=self.owner).delete()
                for i in range(3):
                    self.make_item(name=f"Sedikit {i}")
                few = self.count_queries(headers)
                for i in range(15):
                    self.make_item(name=f"Banyak {i}", is_available=bool(i % 2))
                self.assertEqual(few, self.count_queries(headers))
