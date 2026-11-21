"""Test API DRF Modul 2 (items): daftar, detail, tambah, ubah, hapus, dan "barang saya"."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from items.models import Item
from items.permissions import BORROWED_MESSAGE, FORBIDDEN_MESSAGE
from items.tests.test_models import VALID_DESCRIPTION

User = get_user_model()

PASSWORD = "PasswordTest123."


class ItemAPITestBase(TestCase):
    """Data awal; test tidak berasumsi DB kosong (ada data seed dari migration)."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="api_owner", password=PASSWORD)
        cls.other = User.objects.create_user(username="api_other", password=PASSWORD)
        cls.admin = User.objects.create_user(
            username="api_admin", password=PASSWORD, is_staff=True,
        )
        cls.item = Item.objects.create(
            owner=cls.owner,
            name="Tenda Dome Empat Orang",
            description=VALID_DESCRIPTION,
            category=Item.Category.OUTDOOR,
            condition=Item.Condition.GOOD,
        )
        cls.list_url = reverse("items_api:item-list")
        cls.mine_url = reverse("items_api:item-mine")
        cls.detail_url = reverse("items_api:item-detail", args=[cls.item.pk])
        cls.payload = {
            "name": "Bor Listrik Bosch",
            "description": "Bor listrik lengkap dengan satu set mata bor dan koper.",
            "category": "household",
            "condition": "like_new",
            "image_url": "",
        }

    def setUp(self):
        self.client = APIClient()

    def login(self, user):
        self.client.force_authenticate(user=user)

    def result_ids(self, response):
        return [row["id"] for row in response.data]


class ItemListAPITest(ItemAPITestBase):

    def test_public_list(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.item.pk, self.result_ids(response))

    def test_list_shape_has_no_sensitive_data(self):
        response = self.client.get(self.list_url)
        row = next(r for r in response.data if r["id"] == self.item.pk)
        self.assertEqual(set(row), {
            "id", "name", "description", "category", "category_display", "condition",
            "condition_display", "image_url", "image", "is_available", "is_verified",
            "owner", "created_at",
        })
        self.assertEqual(row["owner"], {"id": self.owner.pk, "username": "api_owner"})
        self.assertEqual(row["category_display"], "Outdoor & Camping")
        # URL absolut agar langsung bisa dipakai klien di luar browser (Flutter).
        self.assertTrue(row["image"].startswith("http://testserver/static/"))

    def test_image_url_overrides_placeholder(self):
        Item.objects.filter(pk=self.item.pk).update(image_url="https://contoh.com/foto.jpg")
        response = self.client.get(self.detail_url)
        self.assertEqual(response.data["image"], "https://contoh.com/foto.jpg")

    def test_search_filter_and_empty_result(self):
        response = self.client.get(self.list_url, {"q": "DOME EMPAT"})
        self.assertEqual(self.result_ids(response), [self.item.pk])
        response = self.client.get(self.list_url, {"q": "tidak-ada-barang-ini"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_category_condition_and_available_filters(self):
        borrowed = Item.objects.create(
            owner=self.owner, name="Kamera Mirrorless", description=VALID_DESCRIPTION,
            category=Item.Category.ELECTRONICS, condition=Item.Condition.FAIR,
            is_available=False,
        )
        ids = self.result_ids(self.client.get(self.list_url, {"category": "outdoor"}))
        self.assertIn(self.item.pk, ids)
        self.assertNotIn(borrowed.pk, ids)
        ids = self.result_ids(self.client.get(self.list_url, {"condition": "fair"}))
        self.assertIn(borrowed.pk, ids)
        self.assertNotIn(self.item.pk, ids)
        ids = self.result_ids(self.client.get(self.list_url, {"available": "true"}))
        self.assertIn(self.item.pk, ids)
        self.assertNotIn(borrowed.pk, ids)

    def test_sort(self):
        response = self.client.get(self.list_url, {"sort": "name"})
        names = [row["name"] for row in response.data]
        self.assertEqual(names, sorted(names))

    def test_hides_deleted_items_and_inactive_owners(self):
        deleted = Item.objects.create(
            owner=self.owner, name="Barang Terhapus", description=VALID_DESCRIPTION,
            category=Item.Category.OTHER, condition=Item.Condition.GOOD,
        )
        deleted.soft_delete()
        ghost = User.objects.create_user(username="api_ghost", password=PASSWORD, is_active=False)
        hidden = Item.objects.create(
            owner=ghost, name="Barang Pemilik Nonaktif", description=VALID_DESCRIPTION,
            category=Item.Category.OTHER, condition=Item.Condition.GOOD,
        )
        ids = self.result_ids(self.client.get(self.list_url))
        self.assertNotIn(deleted.pk, ids)
        self.assertNotIn(hidden.pk, ids)

    def test_list_query_count_is_constant(self):
        with self.assertNumQueries(1):
            self.client.get(self.list_url)


class ItemDetailAPITest(ItemAPITestBase):

    def test_public_detail(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.item.pk)
        self.assertEqual(response.data["name"], self.item.name)

    def test_missing_item_is_404(self):
        url = reverse("items_api:item-detail", args=[999999])
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)

    def test_deleted_item_is_404(self):
        self.item.soft_delete()
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_404_NOT_FOUND)


class ItemCreateAPITest(ItemAPITestBase):

    def test_guest_cannot_create(self):
        before = Item.objects.count()
        response = self.client.post(self.list_url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Item.objects.count(), before)

    def test_logged_in_user_can_create_and_becomes_owner(self):
        self.login(self.other)
        response = self.client.post(self.list_url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item = Item.objects.get(pk=response.data["id"])
        self.assertEqual(item.owner, self.other)
        self.assertTrue(item.is_available)
        self.assertFalse(item.is_verified)
        self.assertEqual(response.data["owner"]["username"], "api_other")

    def test_validation_errors(self):
        self.login(self.owner)
        before = Item.objects.count()
        cases = [
            ({"name": "   "}, "name"),
            ({"name": "ab"}, "name"),
            ({"name": "<b></b>"}, "name"),
            ({"name": "x" * 101}, "name"),
            ({"description": "terlalu pendek"}, "description"),
            ({"description": "<p>pendek</p>" + " " * 30}, "description"),
            ({"category": "tidak-ada"}, "category"),
            ({"condition": "tidak-ada"}, "condition"),
            ({"image_url": "javascript:alert(1)"}, "image_url"),
            ({"image_url": "ftp://contoh.com/foto.jpg"}, "image_url"),
        ]
        for changes, field in cases:
            with self.subTest(changes=changes):
                response = self.client.post(
                    self.list_url, {**self.payload, **changes}, format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
        self.assertEqual(Item.objects.count(), before)

    def test_missing_required_fields(self):
        self.login(self.owner)
        response = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ("name", "description", "category", "condition"):
            self.assertIn(field, response.data)

    def test_html_tags_are_stripped(self):
        self.login(self.owner)
        payload = {**self.payload, "name": "<b>Bor</b> Listrik"}
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Bor Listrik")

    def test_system_fields_are_read_only(self):
        self.login(self.owner)
        response = self.client.post(self.list_url, {
            **self.payload, "is_available": False, "is_verified": True,
            "is_deleted": True, "owner": self.other.pk, "category_display": "palsu",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item = Item.objects.get(pk=response.data["id"])
        self.assertEqual(item.owner, self.owner)
        self.assertTrue(item.is_available)
        self.assertFalse(item.is_verified)
        self.assertFalse(item.is_deleted)
        self.assertEqual(response.data["category_display"], "Perkakas & Rumah Tangga")


class ItemUpdateAPITest(ItemAPITestBase):

    def test_guest_cannot_update_or_delete(self):
        for method in ("patch", "put", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.detail_url, {"name": "Diubah"}, format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_deleted)
        self.assertEqual(self.item.name, "Tenda Dome Empat Orang")

    def test_non_owner_gets_403_with_clear_message(self):
        self.login(self.other)
        for method in ("patch", "put", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.detail_url, {"name": "Diubah"}, format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(response.data["detail"], FORBIDDEN_MESSAGE)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Tenda Dome Empat Orang")

    def test_owner_can_patch_without_touching_other_fields(self):
        self.login(self.owner)
        response = self.client.patch(self.detail_url, {"name": "Tenda Baru"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Tenda Baru")
        self.assertEqual(self.item.description, VALID_DESCRIPTION)

    def test_put_replaces_and_requires_all_fields(self):
        self.login(self.owner)
        response = self.client.put(self.detail_url, {"name": "Tanpa Lainnya"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.put(self.detail_url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Bor Listrik Bosch")
        self.assertEqual(self.item.owner, self.owner)

    def test_update_validation_error(self):
        self.login(self.owner)
        response = self.client.patch(self.detail_url, {"name": "  "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_admin_can_update_any_item(self):
        self.login(self.admin)
        response = self.client.patch(self.detail_url, {"name": "Diubah Admin"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Diubah Admin")
        self.assertEqual(self.item.owner, self.owner)

    def test_cannot_change_system_fields(self):
        self.login(self.owner)
        response = self.client.patch(self.detail_url, {
            "is_available": False, "is_verified": True, "owner": self.other.pk,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_available)
        self.assertFalse(self.item.is_verified)
        self.assertEqual(self.item.owner, self.owner)

    def test_borrowed_item_cannot_be_updated_or_deleted(self):
        Item.objects.filter(pk=self.item.pk).update(is_available=False)
        self.login(self.owner)
        for method in ("patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.detail_url, {"name": "Diubah"}, format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(response.data["detail"], BORROWED_MESSAGE)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_deleted)
        self.assertEqual(self.item.name, "Tenda Dome Empat Orang")

    def test_ownership_checked_before_borrowed_status(self):
        """User lain tidak boleh tahu status peminjaman barang orang lain."""
        Item.objects.filter(pk=self.item.pk).update(is_available=False)
        self.login(self.other)
        response = self.client.patch(self.detail_url, {"name": "Diubah"}, format="json")
        self.assertEqual(response.data["detail"], FORBIDDEN_MESSAGE)

    def test_update_missing_item_is_404(self):
        self.login(self.owner)
        url = reverse("items_api:item-detail", args=[999999])
        self.assertEqual(
            self.client.patch(url, {"name": "Diubah"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )


class ItemDeleteAPITest(ItemAPITestBase):

    def test_owner_delete_is_soft_delete_with_empty_204(self):
        self.login(self.owner)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b"")
        self.assertFalse(Item.objects.filter(pk=self.item.pk).exists())
        # Baris tetap ada untuk riwayat peminjaman (FK loans PROTECT).
        deleted = Item.all_objects.get(pk=self.item.pk)
        self.assertTrue(deleted.is_deleted)
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_delete_any_item(self):
        self.login(self.admin)
        self.assertEqual(self.client.delete(self.detail_url).status_code, 204)
        self.assertTrue(Item.all_objects.get(pk=self.item.pk).is_deleted)


class ItemMineAPITest(ItemAPITestBase):

    def test_requires_login(self):
        self.assertEqual(self.client.get(self.mine_url).status_code, status.HTTP_403_FORBIDDEN)

    def test_only_own_active_items(self):
        mine_deleted = Item.objects.create(
            owner=self.owner, name="Barang Saya Terhapus", description=VALID_DESCRIPTION,
            category=Item.Category.OTHER, condition=Item.Condition.GOOD,
        )
        mine_deleted.soft_delete()
        others = Item.objects.create(
            owner=self.other, name="Barang Orang Lain", description=VALID_DESCRIPTION,
            category=Item.Category.OTHER, condition=Item.Condition.GOOD,
        )
        self.login(self.owner)
        response = self.client.get(self.mine_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.result_ids(response)
        self.assertIn(self.item.pk, ids)
        self.assertNotIn(mine_deleted.pk, ids)
        self.assertNotIn(others.pk, ids)

    def test_mine_supports_search(self):
        self.login(self.owner)
        self.assertEqual(self.client.get(self.mine_url, {"q": "tidak-ada"}).data, [])


class ItemAPIMethodAndCSRFTest(ItemAPITestBase):

    def test_wrong_method_is_405(self):
        self.login(self.owner)
        self.assertEqual(self.client.delete(self.list_url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.post(self.mine_url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_session_write_without_csrf_is_rejected(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username="api_owner", password=PASSWORD))
        before = Item.objects.count()
        response = client.post(self.list_url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Item.objects.count(), before)

    def test_session_write_with_csrf_succeeds(self):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username="api_owner", password=PASSWORD)
        # Halaman katalog (HTML) merender token CSRF ke dalam cookie.
        page = client.get(reverse("items:create"), HTTP_ACCEPT="text/html")
        self.assertEqual(page.status_code, status.HTTP_200_OK)
        token = client.cookies["csrftoken"].value
        response = client.post(
            self.list_url, self.payload, format="json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
