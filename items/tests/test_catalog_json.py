from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.templatetags.static import static
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from items.models import Item
from items.serializers import serialize_item
from items.tests.test_catalog import TOKEN, CatalogTestMixin
from items.tests.test_models import ItemTestMixin
from items.views import CATALOG_PAGE_SIZE

User = get_user_model()

ITEM_KEYS = {
    "id", "name", "description", "category", "category_display", "condition",
    "condition_display", "image_url", "image", "is_available", "is_verified",
    "owner", "created_at",
}


class SerializeItemTest(ItemTestMixin, TestCase):
    """serialize_item(): bentuk data barang untuk JSON (dipakai ulang di Flutter)."""

    def setUp(self):
        self.request = RequestFactory().get("/")

    def test_fields(self):
        item = self.make_item(is_verified=True)
        data = serialize_item(item, self.request)
        self.assertEqual(set(data), ITEM_KEYS)
        self.assertEqual(data["id"], item.pk)
        self.assertEqual(data["name"], item.name)
        self.assertEqual(data["category"], "electronics")
        self.assertEqual(data["category_display"], "Elektronik")
        self.assertEqual(data["condition"], "good")
        self.assertEqual(data["condition_display"], "Baik")
        self.assertTrue(data["is_available"])
        self.assertTrue(data["is_verified"])
        self.assertEqual(datetime.fromisoformat(data["created_at"]), item.created_at)

    def test_owner_only_public_fields(self):
        data = serialize_item(self.make_item(), self.request)
        self.assertEqual(data["owner"], {"id": self.owner.pk, "username": self.owner.username})

    def test_image_uses_image_url(self):
        url = "https://example.com/kipas.jpg"
        data = serialize_item(self.make_item(image_url=url), self.request)
        self.assertEqual(data["image_url"], url)
        self.assertEqual(data["image"], url)

    def test_image_falls_back_to_absolute_placeholder(self):
        data = serialize_item(self.make_item(category=Item.Category.SPORTS), self.request)
        self.assertEqual(data["image_url"], "")
        self.assertEqual(
            data["image"],
            "http://testserver" + static("items/img/placeholders/sports.svg"),
        )


class CatalogJsonTest(CatalogTestMixin, TestCase):
    """Endpoint JSON daftar barang: filter dan pagination sama dengan halaman katalog."""

    def setUp(self):
        self.url = reverse("items:catalog_json")
        now = timezone.now()
        self.camera = self.make_catalog_item(name="Kamera", category=Item.Category.ELECTRONICS)
        self.racket = self.make_catalog_item(
            name="Raket", category=Item.Category.SPORTS, is_available=False,
        )
        Item.objects.filter(pk=self.racket.pk).update(created_at=now - timedelta(days=1))

    def results(self, response):
        return [item["name"] for item in response.json()["results"]]

    def test_url(self):
        self.assertEqual(self.url, "/katalog/json/")

    def test_returns_json_for_anonymous(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_structure(self):
        data = self.get().json()
        self.assertEqual(
            set(data),
            {"count", "num_pages", "page", "page_size", "has_next", "has_previous", "results"},
        )
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], CATALOG_PAGE_SIZE)
        self.assertFalse(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(set(data["results"][0]), ITEM_KEYS)

    def test_default_sort_newest(self):
        self.assertEqual(self.results(self.get()), [self.camera.name, self.racket.name])

    def test_filters_same_as_catalog(self):
        self.assertEqual(self.results(self.get(category="sports")), [self.racket.name])
        self.assertEqual(self.results(self.get(available="1")), [self.camera.name])
        self.assertEqual(self.results(self.get(sort="oldest")), [self.racket.name, self.camera.name])

    def test_invalid_params_ignored(self):
        response = self.get(category="xyz", sort="acak", page="abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

    def test_hidden_items_excluded(self):
        deleted = self.make_catalog_item(name="Terhapus")
        deleted.soft_delete()
        inactive = User.objects.create_user(username="itemtest_json_inactive", is_active=False)
        self.make_catalog_item(name="Nonaktif", owner=inactive)
        self.assertCountEqual(self.results(self.get()), [self.camera.name, self.racket.name])

    def test_no_sensitive_owner_data(self):
        body = self.get().content.decode()
        self.assertNotIn("email", body)
        self.assertNotIn("password", body)

    def test_pagination(self):
        for i in range(CATALOG_PAGE_SIZE):
            self.make_catalog_item(name=f"Halaman {i:02d}")
        first = self.get().json()
        self.assertEqual(first["count"], CATALOG_PAGE_SIZE + 2)
        self.assertEqual(len(first["results"]), CATALOG_PAGE_SIZE)
        self.assertTrue(first["has_next"])
        second = self.get(page=2).json()
        self.assertEqual(second["page"], 2)
        self.assertEqual(len(second["results"]), 2)
        self.assertTrue(second["has_previous"])
        self.assertEqual(self.get(page=999).json()["page"], 2)

    def test_query_count_constant(self):
        def count():
            with CaptureQueriesContext(connection) as ctx:
                self.get()
            return len(ctx.captured_queries)

        few = count()
        for i in range(10):
            owner = User.objects.create_user(username=f"itemtest_json_q_{i}")
            self.make_catalog_item(name=f"Query {i:02d}", owner=owner)
        self.assertEqual(count(), few)

    def test_search_token_used(self):
        # Sanity check: helper get() selalu mempersempit hasil ke barang test.
        self.assertTrue(all(TOKEN in name for name in self.results(self.get())))


class CatalogMethodTest(TestCase):

    def test_catalog_page_rejects_post(self):
        self.assertEqual(self.client.post(reverse("items:catalog")).status_code, 405)
