from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from items.models import Item
from items.tests.test_models import VALID_DESCRIPTION, ItemTestMixin

User = get_user_model()


class ItemAdminTest(ItemTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin_user = User.objects.create_superuser(
            username="itemtest_admin", password="PasswordTest123."
        )
        cls.regular_user = User.objects.create_user(
            username="itemtest_regular", password="PasswordTest123."
        )

    def setUp(self):
        self.client.force_login(self.admin_user)
        self.changelist_url = reverse("admin:items_item_changelist")

    def run_action(self, action, items):
        return self.client.post(
            self.changelist_url,
            {"action": action, "_selected_action": [item.pk for item in items]},
            follow=True,
        )

    # Akses
    def test_changelist_accessible_for_admin(self):
        response = self.client.get(self.changelist_url)
        self.assertEqual(response.status_code, 200)

    def test_changelist_redirects_non_staff_to_login(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(self.changelist_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])

    def test_changelist_includes_deleted_items(self):
        hidden = self.make_item(name="Barang Tersembunyi")
        hidden.soft_delete()
        response = self.client.get(self.changelist_url)
        self.assertIn(hidden, response.context["cl"].queryset)

    def test_search_by_owner_username(self):
        item = self.make_item()
        response = self.client.get(self.changelist_url, {"q": "itemtest_owner"})
        self.assertIn(item, response.context["cl"].queryset)

    # Action moderasi
    def test_hide_action_soft_deletes(self):
        item = self.make_item()
        self.run_action("hide_items", [item])
        self.assertTrue(Item.all_objects.get(pk=item.pk).is_deleted)

    def test_hide_action_forces_borrowed_item(self):
        # Jalur moderasi admin boleh menyembunyikan barang yang sedang dipinjam.
        item = self.make_item(is_available=False)
        self.run_action("hide_items", [item])
        self.assertTrue(Item.all_objects.get(pk=item.pk).is_deleted)

    def test_restore_action(self):
        item = self.make_item()
        item.soft_delete()
        self.run_action("restore_items", [item])
        self.assertFalse(Item.all_objects.get(pk=item.pk).is_deleted)

    def test_verify_action(self):
        item = self.make_item()
        self.run_action("verify_items", [item])
        self.assertTrue(Item.all_objects.get(pk=item.pk).is_verified)

    def test_unverify_action(self):
        item = self.make_item(is_verified=True)
        self.run_action("unverify_items", [item])
        self.assertFalse(Item.all_objects.get(pk=item.pk).is_verified)

    # Hard delete dimatikan
    def test_delete_selected_action_unavailable(self):
        response = self.client.get(self.changelist_url)
        actions = [name for name, _ in response.context["action_form"].fields["action"].choices]
        self.assertNotIn("delete_selected", actions)

    def test_delete_view_forbidden(self):
        item = self.make_item()
        response = self.client.post(reverse("admin:items_item_delete", args=[item.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Item.all_objects.filter(pk=item.pk).exists())

    # Field read-only
    def test_change_form_cannot_modify_protected_fields(self):
        item = self.make_item()
        response = self.client.post(
            reverse("admin:items_item_change", args=[item.pk]),
            {
                "owner": self.owner.pk,
                "name": "Nama Baru Barang",
                "description": VALID_DESCRIPTION,
                "category": Item.Category.ELECTRONICS,
                "condition": Item.Condition.GOOD,
                "image_url": "",
                # is_available dan is_deleted dicoba diubah lewat POST.
                "is_available": "",
                "is_deleted": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        item = Item.all_objects.get(pk=item.pk)
        self.assertEqual(item.name, "Nama Baru Barang")
        self.assertTrue(item.is_available)
        self.assertFalse(item.is_deleted)
