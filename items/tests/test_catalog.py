import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.db import connection
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from items.forms import CatalogFilterForm
from items.models import Item
from items.tests.test_models import ItemTestMixin
from items.views import CATALOG_PAGE_SIZE

User = get_user_model()

# Token unik di nama barang test: katalog bisa berisi data seed, jadi test
# selalu mempersempit hasil lewat pencarian token ini.
TOKEN = "Zqxkat"


class CatalogTestMixin(ItemTestMixin):

    def setUp(self):
        self.url = reverse("items:catalog")

    def make_catalog_item(self, name="Barang", **kwargs):
        return self.make_item(name=f"{TOKEN} {name}", **kwargs)

    def get(self, headers=None, **params):
        params.setdefault("q", TOKEN.lower())
        return self.client.get(self.url, params, headers=headers or {})

    def names(self, response):
        return [item.name for item in response.context["page_obj"].object_list]


class ItemVisibleQuerySetTest(ItemTestMixin, TestCase):
    """Item.objects.visible(): barang yang boleh tampil di katalog."""

    def test_excludes_items_of_inactive_owner(self):
        inactive = User.objects.create_user(username="itemtest_inactive", is_active=False)
        hidden = self.make_item(owner=inactive)
        shown = self.make_item()
        visible = Item.objects.visible()
        self.assertIn(shown, visible)
        self.assertNotIn(hidden, visible)

    def test_excludes_soft_deleted_items(self):
        item = self.make_item()
        item.soft_delete()
        self.assertNotIn(item, Item.objects.visible())


class CatalogFilterFormTest(ItemTestMixin, TestCase):
    """Validasi parameter filter: nilai tidak valid diabaikan, bukan error 500."""

    def setUp(self):
        self.match = self.make_item(
            name=f"{TOKEN} Kamera", category=Item.Category.ELECTRONICS,
            condition=Item.Condition.LIKE_NEW,
        )
        self.other = self.make_item(
            name=f"{TOKEN} Raket", category=Item.Category.SPORTS,
            condition=Item.Condition.GOOD,
        )

    def apply(self, **data):
        data.setdefault("q", TOKEN)
        return list(CatalogFilterForm(data).apply(Item.objects.visible()))

    def test_search_is_stripped(self):
        form = CatalogFilterForm({"q": "  kamera  "})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["q"], "kamera")

    def test_empty_data_returns_all(self):
        self.assertCountEqual(self.apply(), [self.match, self.other])

    def test_invalid_category_is_ignored(self):
        self.assertCountEqual(self.apply(category="xyz"), [self.match, self.other])

    def test_invalid_field_does_not_drop_valid_ones(self):
        self.assertEqual(self.apply(category="xyz", condition=Item.Condition.LIKE_NEW), [self.match])

    def test_search_longer_than_limit_is_ignored(self):
        result = CatalogFilterForm({"q": "a" * 101}).apply(Item.objects.filter(pk=self.match.pk))
        self.assertEqual(list(result), [self.match])

    def test_invalid_sort_falls_back_to_newest(self):
        Item.objects.filter(pk=self.match.pk).update(created_at=timezone.now() - timedelta(days=1))
        self.assertEqual(self.apply(sort="xyz"), [self.other, self.match])


class CatalogPageTest(CatalogTestMixin, TestCase):
    """Halaman katalog: publik, memakai base template, dan sesuai Figma Page 1."""

    def test_url_is_katalog(self):
        self.assertEqual(self.url, "/katalog/")

    def test_anonymous_can_open_catalog(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/catalog.html")
        self.assertTemplateUsed(response, "base.html")

    def test_title_and_heading(self):
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Katalog Barang — ShareSpace</title>")
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, "Katalog Barang Komunitas")

    def test_context_has_page_and_filter_form(self):
        response = self.client.get(self.url)
        self.assertIsInstance(response.context["filter_form"], CatalogFilterForm)
        self.assertEqual(response.context["page_obj"].paginator.per_page, CATALOG_PAGE_SIZE)

    def test_page_size_is_twelve(self):
        self.assertEqual(CATALOG_PAGE_SIZE, 12)

    def test_filter_form_uses_htmx_and_works_without_js(self):
        html = self.client.get(self.url).content.decode()
        form = re.search(r'<form[^>]*id="catalog-filter"[^>]*>', html)
        self.assertIsNotNone(form)
        form_tag = form.group(0)
        self.assertIn('method="get"', form_tag)
        self.assertIn(f'action="{self.url}"', form_tag)
        self.assertIn(f'hx-get="{self.url}"', form_tag)
        self.assertIn('hx-target="#item-list"', form_tag)
        self.assertIn('hx-push-url="true"', form_tag)
        self.assertIn('id="item-list"', html)

    def test_search_input_has_label(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'for="id_q"')
        self.assertContains(response, 'id="id_q"')

    def test_category_chips_cover_all_categories(self):
        response = self.client.get(self.url)
        for value, label in Item.Category.choices:
            with self.subTest(category=value):
                self.assertContains(response, f'value="{value}"')
                self.assertContains(response, escape(label))

    def test_available_only_checkbox(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'name="available"')
        self.assertContains(response, "Tersedia saja")

    def test_active_filters_are_kept_in_form(self):
        html = self.get(
            category=Item.Category.ELECTRONICS, sort="oldest", available="1",
        ).content.decode()
        self.assertRegex(html, r'<input[^>]*value="electronics"[^>]*checked')
        self.assertRegex(html, r'<option value="oldest" selected')
        self.assertRegex(html, r'<input[^>]*name="available"[^>]*checked')
        self.assertIn(f'value="{TOKEN.lower()}"', html)

    def test_user_input_is_escaped(self):
        self.make_catalog_item(name="<script>alert(1)</script>")
        response = self.get()
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_empty_state_when_nothing_matches(self):
        response = self.get(q="tidakadazqx999")
        self.assertContains(response, "empty-state")
        self.assertContains(response, "Tidak ada barang yang cocok")


class CatalogVisibilityTest(CatalogTestMixin, TestCase):
    """Barang tersembunyi tidak boleh muncul; barang yang sedang dipinjam tetap tampil."""

    def test_soft_deleted_item_hidden(self):
        item = self.make_catalog_item(name="Terhapus")
        item.soft_delete()
        self.assertNotIn(item.name, self.names(self.get()))

    def test_item_of_inactive_owner_hidden(self):
        inactive = User.objects.create_user(username="itemtest_cat_inactive", is_active=False)
        item = self.make_catalog_item(name="Pemilik Nonaktif", owner=inactive)
        self.assertNotIn(item.name, self.names(self.get()))

    def test_borrowed_item_still_shown(self):
        item = self.make_catalog_item(name="Dipinjam", is_available=False)
        self.assertIn(item.name, self.names(self.get()))


class CatalogFilterTest(CatalogTestMixin, TestCase):
    """Filter gabungan: kategori + kondisi + ketersediaan + search + sort."""

    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.camera = self.make_catalog_item(
            name="Kamera", category=Item.Category.ELECTRONICS,
            condition=Item.Condition.LIKE_NEW,
        )
        self.speaker = self.make_catalog_item(
            name="Speaker", category=Item.Category.ELECTRONICS,
            condition=Item.Condition.GOOD, is_available=False,
        )
        self.racket = self.make_catalog_item(
            name="Badminton", category=Item.Category.SPORTS,
            condition=Item.Condition.GOOD,
        )
        # created_at dibuat berbeda agar urutan sort bisa diuji pasti.
        for offset, item in enumerate([self.camera, self.speaker, self.racket]):
            Item.objects.filter(pk=item.pk).update(created_at=now - timedelta(days=offset))

    def test_filter_by_category(self):
        names = self.names(self.get(category=Item.Category.ELECTRONICS))
        self.assertCountEqual(names, [self.camera.name, self.speaker.name])

    def test_filter_by_condition(self):
        names = self.names(self.get(condition=Item.Condition.GOOD))
        self.assertCountEqual(names, [self.speaker.name, self.racket.name])

    def test_filter_available_only(self):
        names = self.names(self.get(available="1"))
        self.assertCountEqual(names, [self.camera.name, self.racket.name])

    def test_without_available_shows_borrowed_too(self):
        self.assertIn(self.speaker.name, self.names(self.get()))

    def test_search_by_name_case_insensitive(self):
        names = self.names(self.get(q=f"{TOKEN.upper()} KAMERA"))
        self.assertEqual(names, [self.camera.name])

    def test_search_by_description(self):
        item = self.make_item(
            name="Kompor Portabel",
            description="Kompor gas portabel zqxdesk, cocok untuk camping.",
        )
        self.assertEqual(self.names(self.get(q="zqxdesk")), [item.name])

    def test_combined_filters(self):
        names = self.names(self.get(
            category=Item.Category.ELECTRONICS,
            condition=Item.Condition.LIKE_NEW,
            available="1",
        ))
        self.assertEqual(names, [self.camera.name])

    def test_invalid_params_are_ignored(self):
        response = self.get(category="xyz", condition="rusak", sort="acak")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.names(response)), 3)

    def test_default_sort_newest_first(self):
        self.assertEqual(
            self.names(self.get()),
            [self.camera.name, self.speaker.name, self.racket.name],
        )

    def test_sort_oldest(self):
        self.assertEqual(
            self.names(self.get(sort="oldest")),
            [self.racket.name, self.speaker.name, self.camera.name],
        )

    def test_sort_name_ascending(self):
        self.assertEqual(
            self.names(self.get(sort="name")),
            [self.racket.name, self.camera.name, self.speaker.name],
        )

    def test_sort_name_descending(self):
        self.assertEqual(
            self.names(self.get(sort="name_desc")),
            [self.speaker.name, self.camera.name, self.racket.name],
        )


class CatalogPaginationTest(CatalogTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        for i in range(CATALOG_PAGE_SIZE + 1):
            self.make_catalog_item(name=f"Barang {i:02d}", category=Item.Category.ELECTRONICS)

    def test_first_page_is_full(self):
        response = self.get()
        self.assertEqual(len(self.names(response)), CATALOG_PAGE_SIZE)
        self.assertEqual(response.context["page_obj"].paginator.count, CATALOG_PAGE_SIZE + 1)

    def test_second_page_has_rest(self):
        self.assertEqual(len(self.names(self.get(page=2))), 1)

    def test_invalid_page_falls_back_to_first(self):
        response = self.get(page="abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 1)

    def test_out_of_range_page_shows_last(self):
        response = self.get(page=999)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)

    def test_pagination_keeps_filters_and_uses_htmx(self):
        html = self.get(category=Item.Category.ELECTRONICS).content.decode()
        links = re.findall(r'<a class="pagination-link"[^>]*href="([^"]*page=2[^"]*)"[^>]*>', html)
        self.assertTrue(links)
        self.assertIn(f"q={TOKEN.lower()}", links[0])
        self.assertIn("category=electronics", links[0])
        self.assertIn('hx-target="#item-list"', html)
        self.assertIn("Menampilkan 1–12 dari 13 barang", html)


class CatalogHtmxTest(CatalogTestMixin, TestCase):
    """Request HTMX mendapat partial; request biasa dan history restore mendapat halaman penuh."""

    def setUp(self):
        super().setUp()
        self.item = self.make_catalog_item(name="Tenda")

    def test_htmx_request_returns_partial(self):
        response = self.get(headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/partials/item_list.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertNotContains(response, "<html")
        self.assertContains(response, self.item.name)

    def test_history_restore_returns_full_page(self):
        response = self.get(headers={"HX-Request": "true", "HX-History-Restore-Request": "true"})
        self.assertTemplateUsed(response, "base.html")

    def test_normal_request_returns_full_page(self):
        response = self.get()
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "items/partials/item_list.html")

    def test_response_varies_on_htmx_header(self):
        for headers in ({}, {"HX-Request": "true"}):
            with self.subTest(headers=headers):
                response = self.get(headers=headers)
                self.assertIn("HX-Request", response.headers.get("Vary", ""))


class CatalogQueryTest(CatalogTestMixin, TestCase):
    """Jumlah query tidak bertambah seiring jumlah barang (tanpa N+1 pada owner)."""

    def make_items_with_new_owners(self, start, count):
        for i in range(start, start + count):
            owner = User.objects.create_user(username=f"itemtest_q_{i}")
            self.make_catalog_item(name=f"Query {i:02d}", owner=owner)

    def count_queries(self):
        with CaptureQueriesContext(connection) as ctx:
            self.get()
        return len(ctx.captured_queries)

    def test_query_count_constant(self):
        self.make_items_with_new_owners(0, 3)
        few = self.count_queries()
        self.make_items_with_new_owners(3, 12)
        many = self.count_queries()
        self.assertEqual(few, many)


class ItemCardTest(ItemTestMixin, TestCase):
    """Partial card barang: badge, kondisi, pemilik, dan gambar dengan fallback placeholder."""

    def render_card(self, item):
        return render_to_string("items/partials/item_card.html", {"item": item})

    def test_shows_main_info(self):
        html = self.render_card(self.make_item())
        self.assertIn("Kipas Angin Meja", html)
        self.assertIn("Elektronik", html)
        self.assertIn("Kondisi Baik", html)
        self.assertIn(self.owner.username, html)

    def test_available_badge(self):
        html = self.render_card(self.make_item())
        self.assertIn('class="badge badge-available"', html)
        self.assertIn("Tersedia", html)

    def test_borrowed_badge(self):
        html = self.render_card(self.make_item(is_available=False))
        self.assertIn('class="badge badge-unavailable"', html)
        self.assertIn("Sedang Dipinjam", html)

    def test_verified_badge_only_when_verified(self):
        self.assertNotIn("Terverifikasi", self.render_card(self.make_item()))
        self.assertIn("Terverifikasi", self.render_card(self.make_item(is_verified=True)))

    def test_uses_image_url_with_alt(self):
        html = self.render_card(self.make_item(image_url="https://example.com/kipas.jpg"))
        self.assertRegex(html, r'<img[^>]*src="https://example.com/kipas.jpg"[^>]*alt="Kipas Angin Meja"')

    def test_placeholder_when_no_image_url(self):
        html = self.render_card(self.make_item(category=Item.Category.SPORTS))
        self.assertIn(f'src="{static("items/img/placeholders/sports.svg")}"', html)

    def test_placeholder_exists_for_every_category(self):
        for value, _ in Item.Category.choices:
            with self.subTest(category=value):
                self.assertIsNotNone(finders.find(f"items/img/placeholders/{value}.svg"))
