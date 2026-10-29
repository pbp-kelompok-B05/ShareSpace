"""Test data seed (migration 0002_seed_data): user dummy demo_* dan barang sintetis.

DB test bisa berisi data lain, jadi semua query dipersempit ke username dan
pasangan (owner, name) dari seed_data.json; tidak ada asumsi jumlah total.
"""
import importlib
import json
import operator
from functools import cache, reduce
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.models import ProtectedError, Q
from django.test import TestCase
from django.urls import reverse

from authentication.models import UserProfile
from items.models import Item
from items.tests.test_models import VALID_DESCRIPTION

User = get_user_model()

SEED_FILE = Path(__file__).resolve().parent.parent / "seed_data.json"
SEED_MIGRATION = ("items", "0002_seed_data")

ACTIVE_SEED_ITEMS = 50
INACTIVE_SEED_ITEMS = 3
VERIFIED_SEED_ITEMS = 8


@cache
def seed_data():
    with SEED_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def seed_usernames(active=None):
    return [
        u["username"] for u in seed_data()["users"]
        if active is None or u["is_active"] == active
    ]


def seed_items_q(entries=None):
    """Q yang mencocokkan tepat barang seed: pasangan (owner, name) dari JSON."""
    entries = seed_data()["items"] if entries is None else entries
    return reduce(operator.or_, (Q(owner__username=e["owner"], name=e["name"]) for e in entries))


def seed_items():
    """Semua barang seed, termasuk yang sudah di-soft delete."""
    return Item.all_objects.filter(seed_items_q())


class SeedUsersTest(TestCase):

    def test_all_seed_users_exist(self):
        found = set(User.objects.filter(username__in=seed_usernames()).values_list("username", flat=True))
        self.assertEqual(found, set(seed_usernames()))

    def test_usernames_use_demo_prefix(self):
        # Prefix mencegah get_or_create menempelkan barang seed ke akun asli di PWS.
        for username in seed_usernames():
            self.assertTrue(username.startswith("demo_"), username)

    def test_seed_users_cannot_log_in(self):
        for user in User.objects.filter(username__in=seed_usernames()):
            self.assertFalse(user.has_usable_password(), user.username)

    def test_seed_users_are_not_admin(self):
        users = User.objects.filter(username__in=seed_usernames())
        self.assertFalse(users.filter(Q(is_staff=True) | Q(is_superuser=True)).exists())

    def test_six_active_and_one_inactive_user(self):
        users = User.objects.filter(username__in=seed_usernames())
        self.assertEqual(users.filter(is_active=True).count(), 6)
        self.assertEqual(users.filter(is_active=False).count(), 1)

    def test_each_seed_user_has_profile_with_full_name(self):
        for entry in seed_data()["users"]:
            profile = UserProfile.objects.get(user__username=entry["username"])
            self.assertEqual(profile.full_name, entry["full_name"])
            self.assertTrue(profile.full_name)


class SeedItemsTest(TestCase):

    def test_json_owners_are_seed_users_and_pairs_unique(self):
        pairs = [(e["owner"], e["name"]) for e in seed_data()["items"]]
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertTrue({owner for owner, _ in pairs} <= set(seed_usernames()))

    def test_all_seed_items_exist(self):
        self.assertEqual(seed_items().count(), ACTIVE_SEED_ITEMS + INACTIVE_SEED_ITEMS)

    def test_fifty_seed_items_visible_in_catalog(self):
        visible = Item.objects.visible().filter(seed_items_q())
        self.assertEqual(visible.count(), ACTIVE_SEED_ITEMS)

    def test_items_of_inactive_user_hidden(self):
        inactive = seed_usernames(active=False)
        hidden = seed_items().filter(owner__username__in=inactive)
        self.assertEqual(hidden.count(), INACTIVE_SEED_ITEMS)
        self.assertFalse(Item.objects.visible().filter(pk__in=hidden).exists())

        item = hidden.first()
        response = self.client.get(reverse("items:catalog"), {"q": item.name})
        self.assertNotIn(item, response.context["page_obj"].object_list)

    def test_every_seed_item_passes_model_validation(self):
        for item in seed_items():
            with self.subTest(item=item.name):
                item.full_clean()

    def test_covers_all_categories_and_conditions(self):
        visible = Item.objects.visible().filter(seed_items_q())
        self.assertEqual(set(visible.values_list("category", flat=True)), set(Item.Category.values))
        self.assertEqual(set(visible.values_list("condition", flat=True)), set(Item.Condition.values))

    def test_all_available_not_deleted_and_without_image(self):
        # is_available hanya diubah modul loans; seed tidak membuat barang "Dipinjam" tanpa Loan.
        items = seed_items()
        self.assertFalse(items.filter(is_available=False).exists())
        self.assertFalse(items.filter(is_deleted=True).exists())
        self.assertFalse(items.exclude(image_url="").exists())

    def test_exactly_eight_verified(self):
        self.assertEqual(seed_items().filter(is_verified=True).count(), VERIFIED_SEED_ITEMS)

    def test_created_at_follows_days_ago(self):
        days_ago = {(e["owner"], e["name"]): e["days_ago"] for e in seed_data()["items"]}
        ordered = seed_items().select_related("owner").order_by("created_at")
        days = [days_ago[(item.owner.username, item.name)] for item in ordered]
        # Dari yang tertua ke terbaru, days_ago tidak pernah naik.
        self.assertEqual(days, sorted(days, reverse=True))
        self.assertGreater(len(set(days)), 1)


class SeedLoaderTest(TestCase):
    """seed_forward/seed_reverse dijalankan langsung dengan model historis migration 0002."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = importlib.import_module("items.migrations.0002_seed_data")
        cls.state_apps = MigrationLoader(connection).project_state(SEED_MIGRATION).apps

    def forward(self):
        self.migration.seed_forward(self.state_apps, None)

    def reverse(self):
        self.migration.seed_reverse(self.state_apps, None)

    def counts(self):
        return (
            User.objects.filter(username__in=seed_usernames()).count(),
            UserProfile.objects.filter(user__username__in=seed_usernames()).count(),
            seed_items().count(),
        )

    def test_forward_is_idempotent(self):
        before = self.counts()
        self.forward()
        self.assertEqual(self.counts(), before)

    def test_forward_keeps_soft_deleted_seed_item_deleted(self):
        item = seed_items().first()
        item.soft_delete()
        self.forward()
        same = Item.all_objects.filter(owner=item.owner, name=item.name)
        self.assertEqual(same.count(), 1)
        self.assertTrue(same.get().is_deleted)

    def test_forward_does_not_change_existing_seed_item(self):
        # Perubahan admin setelah seed (mis. cabut verifikasi) tidak ditimpa saat forward dijalankan ulang.
        item = seed_items().first()
        flipped = not item.is_verified
        Item.all_objects.filter(pk=item.pk).update(is_verified=flipped)
        self.forward()
        item.refresh_from_db()
        self.assertEqual(item.is_verified, flipped)

    def test_reverse_removes_only_seed_data(self):
        other = User.objects.create_user(username="itemtest_seed_other", password="PasswordTest123.")
        kept = Item.objects.create(
            owner=other, name="Barang Bukan Seed", description=VALID_DESCRIPTION,
            category=Item.Category.OTHER, condition=Item.Condition.GOOD,
        )
        self.reverse()
        self.assertEqual(self.counts(), (0, 0, 0))
        self.assertTrue(Item.objects.filter(pk=kept.pk).exists())
        self.assertTrue(User.objects.filter(pk=other.pk).exists())

    def test_forward_after_reverse_restores_seed(self):
        before = self.counts()
        self.reverse()
        self.forward()
        self.assertEqual(self.counts(), before)

    def test_reverse_fails_when_seed_user_still_owns_other_item(self):
        # owner memakai PROTECT: reverse sengaja gagal, bukan menghapus barang non-seed.
        owner = User.objects.get(username=seed_usernames(active=True)[0])
        Item.objects.create(
            owner=owner, name="Barang Tambahan Non Seed", description=VALID_DESCRIPTION,
            category=Item.Category.OTHER, condition=Item.Condition.GOOD,
        )
        before = self.counts()
        with self.assertRaises(ProtectedError), transaction.atomic():
            self.reverse()
        # Migration berjalan dalam transaksi, jadi kegagalan tidak meninggalkan data setengah terhapus.
        self.assertEqual(self.counts(), before)
