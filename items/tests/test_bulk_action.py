import json

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from items.forms import BulkItemActionForm
from items.models import Item
from items.tests.test_decorators import TEST_CACHES
from items.tests.test_models import ItemTestMixin
from items.views import ITEM_BULK_RATE_LIMIT, ITEM_UPDATE_RATE_LIMIT

User = get_user_model()

HTMX_HEADERS = {"HX-Request": "true"}
NOT_OWNED_MESSAGE = "Ada barang yang tidak ditemukan atau bukan milikmu."
EMPTY_MESSAGE = "Pilih minimal satu barang."


class BulkActionTestMixin(ItemTestMixin):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other = User.objects.create_user(username="itemtest_bulk_other")
        cls.staff = User.objects.create_user(username="itemtest_bulk_staff", is_staff=True)

    def setUp(self):
        cache.clear()
        self.url = reverse("items:bulk_action")
        self.my_items_url = reverse("items:my_items")

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def post(self, action="delete", items=(), htmx=False, **extra):
        data = {"action": action, "items": [getattr(i, "pk", i) for i in items], **extra}
        return self.client.post(self.url, data, headers=HTMX_HEADERS if htmx else {})

    def toast(self, response):
        return json.loads(response["HX-Trigger"])["showToast"]

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def deleted(self, item):
        return Item.all_objects.get(pk=item.pk).is_deleted


class BulkItemActionFormTest(BulkActionTestMixin, TestCase):
    """Pilihan barang dibatasi ke milik user; satu pk asing membuat seluruh form tidak valid."""

    def form(self, user=None, **data):
        return BulkItemActionForm(user or self.owner, data)

    def test_valid_with_own_items(self):
        item = self.make_item()
        form = self.form(action="delete", items=[item.pk])
        self.assertTrue(form.is_valid(), form.errors)

    def test_queryset_limited_to_owner_including_deleted(self):
        own = self.make_item()
        deleted = self.make_item()
        deleted.soft_delete()
        theirs = self.make_item(owner=self.other)
        queryset = self.form().fields["items"].queryset
        self.assertIn(own, queryset)
        self.assertIn(Item.all_objects.get(pk=deleted.pk), queryset)
        self.assertNotIn(theirs, queryset)

    def test_foreign_item_invalidates_form(self):
        own = self.make_item()
        theirs = self.make_item(owner=self.other)
        form = self.form(action="delete", items=[own.pk, theirs.pk])
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["items"], [NOT_OWNED_MESSAGE])

    def test_empty_selection_invalid(self):
        form = self.form(action="delete")
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["items"], [EMPTY_MESSAGE])

    def test_non_numeric_pk_invalid(self):
        self.assertFalse(self.form(action="delete", items=["abc"]).is_valid())

    def test_invalid_action(self):
        item = self.make_item()
        form = self.form(action="verify", items=[item.pk])
        self.assertFalse(form.is_valid())
        self.assertIn("action", form.errors)

    def test_max_items(self):
        self.assertEqual(BulkItemActionForm.MAX_ITEMS, 100)
        items = Item.objects.bulk_create([self.build_item() for _ in range(101)])
        form = self.form(action="delete", items=[i.pk for i in items])
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["items"], ["Maksimal 100 barang per aksi."])

    def test_save_returns_changed_and_skipped(self):
        available = self.make_item()
        borrowed = self.make_item(is_available=False)
        form = self.form(action="delete", items=[available.pk, borrowed.pk])
        self.assertTrue(form.is_valid())
        self.assertEqual(form.save(), (1, 1))


@override_settings(CACHES=TEST_CACHES)
class BulkActionAccessTest(BulkActionTestMixin, TestCase):
    """Wajib login, hanya POST, CSRF ditegakkan, hanya barang milik sendiri (termasuk untuk admin)."""

    def setUp(self):
        super().setUp()
        self.item = self.make_item()

    def test_url(self):
        self.assertEqual(self.url, "/katalog/saya/aksi/")

    def test_anonymous_redirected_to_login_and_nothing_changes(self):
        response = self.post(items=[self.item])
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("authentication:login")))
        self.assertFalse(self.deleted(self.item))

    def test_anonymous_htmx_gets_hx_redirect(self):
        response = self.post(items=[self.item], htmx=True)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(response["HX-Redirect"].startswith(reverse("authentication:login")))

    def test_get_not_allowed(self):
        self.login()
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post(self.url, {"action": "delete", "items": [self.item.pk]})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.deleted(self.item))

    def test_other_user_cannot_delete(self):
        self.login(self.other)
        response = self.post(items=[self.item], htmx=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.toast(response), {"message": NOT_OWNED_MESSAGE, "level": "error"})
        self.assertFalse(self.deleted(self.item))

    def test_staff_cannot_bulk_delete_other_users_items(self):
        # Moderasi admin lewat Django admin; bulk action hanya untuk barang milik sendiri.
        self.login(self.staff)
        self.assertEqual(self.post(items=[self.item], htmx=True).status_code, 400)
        self.assertFalse(self.deleted(self.item))

    def test_mixed_own_and_foreign_changes_nothing(self):
        theirs = self.make_item(owner=self.other)
        self.login()
        response = self.post(items=[self.item, theirs], htmx=True)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.deleted(self.item))
        self.assertFalse(self.deleted(theirs))

    def test_nonexistent_item_rejected(self):
        self.login()
        self.assertEqual(self.post(items=[self.item.pk, 999999], htmx=True).status_code, 400)
        self.assertFalse(self.deleted(self.item))


@override_settings(CACHES=TEST_CACHES)
class BulkDeleteTest(BulkActionTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.login()
        self.first = self.make_item(name="Tenda Dome")
        self.second = self.make_item(name="Kompor Portabel")
        self.untouched = self.make_item(name="Matras Gulung")

    def test_selected_items_soft_deleted(self):
        self.post(items=[self.first, self.second])
        self.assertTrue(self.deleted(self.first))
        self.assertTrue(self.deleted(self.second))
        self.assertFalse(self.deleted(self.untouched))
        # Baris tetap ada (FK loans memakai PROTECT).
        self.assertEqual(Item.all_objects.filter(pk__in=[self.first.pk, self.second.pk]).count(), 2)

    def test_non_htmx_redirects_with_message(self):
        response = self.post(items=[self.first, self.second])
        self.assertRedirects(response, self.my_items_url)
        self.assertEqual(self.messages(response), ["2 barang dihapus."])

    def test_htmx_returns_list_partial_and_toast(self):
        response = self.post(items=[self.first], htmx=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/partials/my_item_list.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertEqual(self.toast(response), {"message": "1 barang dihapus.", "level": "success"})
        self.assertNotContains(response, "Tenda Dome")
        self.assertContains(response, "Matras Gulung")
        # Toast sudah lewat HX-Trigger; jangan antre lagi di Django messages.
        self.assertEqual(self.messages(response), [])

    def test_borrowed_item_skipped(self):
        borrowed = self.make_item(name="Sedang Dipinjam", is_available=False)
        response = self.post(items=[self.first, borrowed], htmx=True)
        self.assertTrue(self.deleted(self.first))
        self.assertFalse(self.deleted(borrowed))
        self.assertEqual(self.toast(response), {
            "message": "1 barang dihapus. 1 barang dilewati karena sedang dipinjam.",
            "level": "success",
        })

    def test_only_borrowed_items_gives_warning(self):
        borrowed = self.make_item(is_available=False)
        response = self.post(items=[borrowed], htmx=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.toast(response), {
            "message": "Tidak ada barang yang dihapus. 1 barang dilewati karena sedang dipinjam.",
            "level": "warning",
        })

    def test_empty_selection_htmx(self):
        response = self.post(htmx=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.toast(response), {"message": EMPTY_MESSAGE, "level": "error"})

    def test_invalid_form_non_htmx_redirects_with_error(self):
        response = self.post()
        self.assertRedirects(response, self.my_items_url)
        self.assertEqual(self.messages(response), [EMPTY_MESSAGE])

    def test_response_keeps_filters_and_page_from_post(self):
        response = self.post(items=[self.first], htmx=True, q="kompor", sort="name", page="1")
        form = response.context["filter_form"]
        self.assertEqual(form.cleaned_data["q"], "kompor")
        self.assertEqual([i.name for i in response.context["page_obj"].object_list], ["Kompor Portabel"])

    def test_response_updates_stats_out_of_band(self):
        response = self.post(items=[self.first, self.second], htmx=True)
        html = response.content.decode()
        self.assertRegex(html, r'<dl[^>]*id="my-items-stats"[^>]*hx-swap-oob="true"')
        self.assertRegex(html, r"Total barang</dt>\s*<dd[^>]*>1</dd>")

    def test_query_count_constant(self):
        def count(n):
            items = [self.make_item(name=f"Massal {n}-{i}") for i in range(n)]
            with CaptureQueriesContext(connection) as ctx:
                self.post(items=items, htmx=True)
            return len(ctx.captured_queries)

        self.assertEqual(count(2), count(20))


@override_settings(CACHES=TEST_CACHES)
class BulkRestoreTest(BulkActionTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.login()
        self.item = self.make_item(name="Tenda Dome")
        self.item.soft_delete()

    def test_restores_own_deleted_item(self):
        self.post("restore", items=[self.item])
        self.assertFalse(self.deleted(self.item))
        self.assertIsNone(Item.objects.get(pk=self.item.pk).deleted_at)

    def test_non_htmx_redirects_to_deleted_tab(self):
        response = self.post("restore", items=[self.item])
        self.assertRedirects(response, f"{self.my_items_url}?status=deleted")
        self.assertEqual(self.messages(response), ["1 barang dipulihkan."])

    def test_htmx_rerenders_deleted_tab(self):
        other_deleted = self.make_item(name="Kompor Lama")
        other_deleted.soft_delete()
        response = self.post("restore", items=[self.item], htmx=True, status="deleted")
        self.assertEqual(self.toast(response), {"message": "1 barang dipulihkan.", "level": "success"})
        names = [i.name for i in response.context["page_obj"].object_list]
        self.assertEqual(names, ["Kompor Lama"])

    def test_item_not_deleted_is_skipped(self):
        active = self.make_item()
        response = self.post("restore", items=[self.item, active], htmx=True)
        self.assertEqual(self.toast(response)["message"], "1 barang dipulihkan. 1 barang dilewati karena belum dihapus.")

    def test_cannot_restore_other_users_item(self):
        theirs = self.make_item(owner=self.other)
        theirs.soft_delete()
        self.assertEqual(self.post("restore", items=[theirs], htmx=True).status_code, 400)
        self.assertTrue(self.deleted(theirs))


@override_settings(CACHES=TEST_CACHES)
class BulkRateLimitTest(BulkActionTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.login()
        self.item = self.make_item()

    def test_limit_value(self):
        self.assertEqual(ITEM_BULK_RATE_LIMIT, 60)

    def test_post_over_limit_is_429(self):
        for _ in range(ITEM_BULK_RATE_LIMIT):
            self.post("restore", items=[self.item], htmx=True)
        response = self.post("restore", items=[self.item], htmx=True)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)

    def test_scope_separate_from_item_update(self):
        edit_url = reverse("items:edit", args=[self.item.pk])
        for _ in range(ITEM_UPDATE_RATE_LIMIT + 1):
            self.client.post(edit_url, {})
        self.assertEqual(self.post("restore", items=[self.item], htmx=True).status_code, 200)
