from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from items.models import Item

User = get_user_model()

VALID_DESCRIPTION = "Kipas angin meja, masih kencang dan tidak berisik."


class ItemTestMixin:
    """Helper pembuatan data; tidak berasumsi DB kosong (ada data seed)."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="itemtest_owner", password="PasswordTest123."
        )

    def make_item(self, **kwargs):
        data = {
            "owner": self.owner,
            "name": "Kipas Angin Meja",
            "description": VALID_DESCRIPTION,
            "category": Item.Category.ELECTRONICS,
            "condition": Item.Condition.GOOD,
        }
        data.update(kwargs)
        return Item.objects.create(**data)

    def build_item(self, **kwargs):
        """Instance belum disimpan, untuk menguji full_clean()."""
        data = {
            "owner": self.owner,
            "name": "Kipas Angin Meja",
            "description": VALID_DESCRIPTION,
            "category": Item.Category.ELECTRONICS,
            "condition": Item.Condition.GOOD,
        }
        data.update(kwargs)
        return Item(**data)

    def assertFieldInvalid(self, field, **kwargs):
        with self.assertRaises(ValidationError) as ctx:
            self.build_item(**kwargs).full_clean()
        self.assertIn(field, ctx.exception.message_dict)

    def assertValid(self, **kwargs):
        self.build_item(**kwargs).full_clean()


class ItemDefaultsTest(ItemTestMixin, TestCase):
    def test_default_values(self):
        item = self.make_item()
        self.assertTrue(item.is_available)
        self.assertFalse(item.is_verified)
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)
        self.assertEqual(item.image_url, "")
        self.assertIsNotNone(item.created_at)
        self.assertIsNotNone(item.updated_at)

    def test_str_returns_name(self):
        self.assertEqual(str(self.make_item(name="Tenda Dome")), "Tenda Dome")

    def test_owner_related_name(self):
        item = self.make_item()
        self.assertIn(item, self.owner.items.all())

    def test_ordering_newest_first(self):
        older = self.make_item(name="Barang Lama")
        newer = self.make_item(name="Barang Baru")
        Item.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        pks = list(
            Item.objects.filter(pk__in=[older.pk, newer.pk]).values_list("pk", flat=True)
        )
        self.assertEqual(pks, [newer.pk, older.pk])


class ItemChoicesTest(TestCase):
    def test_category_labels(self):
        self.assertEqual(
            Item.Category.labels,
            [
                "Elektronik",
                "Perkakas & Rumah Tangga",
                "Olahraga",
                "Buku & Alat Tulis",
                "Hobi & Musik",
                "Outdoor & Camping",
                "Lainnya",
            ],
        )

    def test_condition_labels(self):
        self.assertEqual(
            Item.Condition.labels, ["Seperti Baru", "Baik", "Layak Pakai"]
        )


class ItemValidationTest(ItemTestMixin, TestCase):
    def test_valid_item_passes(self):
        self.assertValid()

    # name: 3-100 karakter
    def test_name_too_short(self):
        self.assertFieldInvalid("name", name="ab")

    def test_name_min_length_boundary(self):
        self.assertValid(name="abc")

    def test_name_max_length_boundary(self):
        self.assertValid(name="a" * 100)

    def test_name_too_long(self):
        self.assertFieldInvalid("name", name="a" * 101)

    def test_name_whitespace_only(self):
        self.assertFieldInvalid("name", name="     ")

    def test_name_padded_with_spaces_counts_stripped_length(self):
        self.assertFieldInvalid("name", name="  ab  ")

    # description: 20-1000 karakter
    def test_description_too_short(self):
        self.assertFieldInvalid("description", description="a" * 19)

    def test_description_min_length_boundary(self):
        self.assertValid(description="a" * 20)

    def test_description_max_length_boundary(self):
        self.assertValid(description="a" * 1000)

    def test_description_too_long(self):
        self.assertFieldInvalid("description", description="a" * 1001)

    def test_description_whitespace_only(self):
        self.assertFieldInvalid("description", description=" " * 30)

    # category & condition
    def test_invalid_category(self):
        self.assertFieldInvalid("category", category="senjata")

    def test_invalid_condition(self):
        self.assertFieldInvalid("condition", condition="rusak")

    def test_category_required(self):
        self.assertFieldInvalid("category", category="")

    # image_url: opsional, maks 500, hanya http/https
    def test_image_url_optional(self):
        self.assertValid(image_url="")

    def test_image_url_https_valid(self):
        self.assertValid(image_url="https://example.com/kipas.jpg")

    def test_image_url_http_valid(self):
        self.assertValid(image_url="http://example.com/kipas.jpg")

    def test_image_url_max_length_boundary(self):
        base = "https://example.com/"
        self.assertValid(image_url=base + "a" * (500 - len(base)))

    def test_image_url_too_long(self):
        base = "https://example.com/"
        self.assertFieldInvalid("image_url", image_url=base + "a" * (501 - len(base)))

    def test_image_url_rejects_ftp(self):
        self.assertFieldInvalid("image_url", image_url="ftp://example.com/kipas.jpg")

    def test_image_url_rejects_javascript(self):
        self.assertFieldInvalid("image_url", image_url="javascript:alert(1)")

    def test_image_url_rejects_non_url(self):
        self.assertFieldInvalid("image_url", image_url="bukan url")


class ItemManagerTest(ItemTestMixin, TestCase):
    def test_default_manager_hides_deleted(self):
        visible = self.make_item(name="Terlihat")
        hidden = self.make_item(name="Tersembunyi")
        hidden.soft_delete()
        qs = Item.objects.filter(pk__in=[visible.pk, hidden.pk])
        self.assertQuerySetEqual(qs, [visible])

    def test_all_objects_includes_deleted(self):
        hidden = self.make_item()
        hidden.soft_delete()
        self.assertTrue(Item.all_objects.filter(pk=hidden.pk).exists())

    def test_base_manager_includes_deleted(self):
        # Akses FK dari loans (loan.item) memakai _base_manager.
        hidden = self.make_item()
        hidden.soft_delete()
        self.assertEqual(Item._base_manager.get(pk=hidden.pk), hidden)

    def test_related_manager_hides_deleted(self):
        hidden = self.make_item()
        hidden.soft_delete()
        self.assertNotIn(hidden, self.owner.items.all())


class ItemSoftDeleteTest(ItemTestMixin, TestCase):
    def test_soft_delete_sets_flags(self):
        item = self.make_item()
        item.soft_delete()
        item = Item.all_objects.get(pk=item.pk)
        self.assertTrue(item.is_deleted)
        self.assertIsNotNone(item.deleted_at)

    def test_soft_delete_keeps_row(self):
        item = self.make_item()
        item.soft_delete()
        self.assertTrue(Item.all_objects.filter(pk=item.pk).exists())

    def test_soft_delete_is_idempotent(self):
        item = self.make_item()
        item.soft_delete()
        first_deleted_at = Item.all_objects.get(pk=item.pk).deleted_at
        item.soft_delete()
        self.assertEqual(Item.all_objects.get(pk=item.pk).deleted_at, first_deleted_at)

    def test_soft_delete_rejects_borrowed_item(self):
        item = self.make_item(is_available=False)
        with self.assertRaises(ValidationError):
            item.soft_delete()
        item = Item.all_objects.get(pk=item.pk)
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)

    def test_soft_delete_force_allows_borrowed_item(self):
        # Jalur moderasi admin (kasus laporan).
        item = self.make_item(is_available=False)
        item.soft_delete(force=True)
        item = Item.all_objects.get(pk=item.pk)
        self.assertTrue(item.is_deleted)
        self.assertIsNotNone(item.deleted_at)

    def test_restore(self):
        item = self.make_item()
        item.soft_delete()
        item.restore()
        item = Item.objects.get(pk=item.pk)
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)


class ItemQuerySetBulkTest(ItemTestMixin, TestCase):
    """Versi massal soft_delete()/restore() untuk bulk action: satu UPDATE, aturan tetap di model."""

    def test_soft_delete_updates_available_items(self):
        items = [self.make_item(), self.make_item()]
        count = Item.objects.filter(pk__in=[i.pk for i in items]).soft_delete()
        self.assertEqual(count, 2)
        for item in Item.all_objects.filter(pk__in=[i.pk for i in items]):
            self.assertTrue(item.is_deleted)
            self.assertIsNotNone(item.deleted_at)

    def test_soft_delete_skips_borrowed_items(self):
        borrowed = self.make_item(is_available=False)
        count = Item.objects.filter(pk=borrowed.pk).soft_delete()
        self.assertEqual(count, 0)
        borrowed.refresh_from_db()
        self.assertFalse(borrowed.is_deleted)

    def test_soft_delete_skips_already_deleted_items(self):
        item = self.make_item()
        item.soft_delete()
        deleted_at = Item.all_objects.get(pk=item.pk).deleted_at
        self.assertEqual(Item.all_objects.filter(pk=item.pk).soft_delete(), 0)
        self.assertEqual(Item.all_objects.get(pk=item.pk).deleted_at, deleted_at)

    def test_soft_delete_updates_timestamp(self):
        item = self.make_item()
        Item.objects.filter(pk=item.pk).update(updated_at=timezone.now() - timedelta(days=1))
        Item.objects.filter(pk=item.pk).soft_delete()
        self.assertGreater(Item.all_objects.get(pk=item.pk).updated_at, timezone.now() - timedelta(minutes=1))

    def test_soft_delete_runs_single_query(self):
        items = [self.make_item() for _ in range(3)]
        queryset = Item.objects.filter(pk__in=[i.pk for i in items])
        with self.assertNumQueries(1):
            queryset.soft_delete()

    def test_restore_updates_deleted_items(self):
        item = self.make_item()
        item.soft_delete()
        self.assertEqual(Item.all_objects.filter(pk=item.pk).restore(), 1)
        item.refresh_from_db()
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)

    def test_restore_skips_items_not_deleted(self):
        item = self.make_item()
        self.assertEqual(Item.all_objects.filter(pk=item.pk).restore(), 0)

    def test_restore_through_default_manager_finds_nothing(self):
        # Manager default menyaring barang terhapus, jadi pemulihan harus lewat all_objects.
        item = self.make_item()
        item.soft_delete()
        self.assertEqual(Item.objects.filter(pk=item.pk).restore(), 0)

    def test_all_objects_has_custom_queryset(self):
        self.assertTrue(hasattr(Item.all_objects.all(), "visible"))


class ItemConstraintTest(ItemTestMixin, TestCase):
    def test_deleted_without_deleted_at_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_item(is_deleted=True, deleted_at=None)

    def test_deleted_at_without_deleted_flag_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_item(is_deleted=False, deleted_at=timezone.now())

    def test_deleting_owner_with_items_is_protected(self):
        self.make_item()
        with self.assertRaises(ProtectedError):
            self.owner.delete()


class ItemPermissionTest(ItemTestMixin, TestCase):
    """can_be_managed_by(): hanya pemilik atau admin (is_staff) yang boleh mengelola barang."""

    def test_owner_can_manage(self):
        self.assertTrue(self.make_item().can_be_managed_by(self.owner))

    def test_staff_can_manage_other_users_item(self):
        staff = User.objects.create_user(username="itemtest_staff", is_staff=True)
        self.assertTrue(self.make_item().can_be_managed_by(staff))

    def test_other_user_cannot_manage(self):
        other = User.objects.create_user(username="itemtest_other")
        self.assertFalse(self.make_item().can_be_managed_by(other))

    def test_anonymous_cannot_manage(self):
        self.assertFalse(self.make_item().can_be_managed_by(AnonymousUser()))
