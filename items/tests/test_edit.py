import json

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from items.forms import ItemForm
from items.models import Item
from items.tests.test_create import valid_data
from items.tests.test_decorators import BORROWED_MESSAGE, FORBIDDEN_MESSAGE, TEST_CACHES
from items.tests.test_models import ItemTestMixin
from items.views import ITEM_CREATE_RATE_LIMIT, ITEM_UPDATE_RATE_LIMIT

User = get_user_model()

HTMX_HEADERS = {"HX-Request": "true"}
UPDATED_DESCRIPTION = "Kipas angin meja tiga kecepatan, baru diservis dan tidak berisik."


class ItemEditTestMixin(ItemTestMixin):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other = User.objects.create_user(username="itemtest_edit_other")
        cls.staff = User.objects.create_user(username="itemtest_edit_staff", is_staff=True)

    def setUp(self):
        cache.clear()
        self.item = self.make_item()
        self.url = reverse("items:edit", args=[self.item.pk])
        self.detail_url = reverse("items:detail", args=[self.item.pk])

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def get(self, htmx=False):
        return self.client.get(self.url, headers=HTMX_HEADERS if htmx else {})

    def post(self, data=None, htmx=False, url=None, **kwargs):
        if data is None:
            data = valid_data(name="Kipas Angin Berdiri", description=UPDATED_DESCRIPTION)
        headers = HTMX_HEADERS if htmx else {}
        return self.client.post(url or self.url, data, headers=headers, **kwargs)

    def toast(self, response):
        return json.loads(response["HX-Trigger"])["showToast"]


@override_settings(CACHES=TEST_CACHES)
class ItemEditAccessTest(ItemEditTestMixin, TestCase):
    """Hanya pemilik atau admin yang bisa membuka/mengirim form edit; barang dipinjam terkunci."""

    def test_url(self):
        self.assertEqual(self.url, f"/katalog/{self.item.pk}/edit/")

    def test_anonymous_redirected_to_login(self):
        response = self.get()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("authentication:login")))

    def test_anonymous_htmx_gets_hx_redirect(self):
        response = self.get(htmx=True)
        self.assertEqual(response.status_code, 204)
        self.assertIn("HX-Redirect", response)

    def test_other_user_forbidden(self):
        self.login(self.other)
        response = self.get()
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, FORBIDDEN_MESSAGE, status_code=403)

    def test_other_user_post_does_not_change_item(self):
        self.login(self.other)
        response = self.post()
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Kipas Angin Meja")

    def test_other_user_htmx_gets_toast(self):
        self.login(self.other)
        response = self.post(htmx=True)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.toast(response)["message"], FORBIDDEN_MESSAGE)

    def test_staff_can_open_form(self):
        self.login(self.staff)
        self.assertEqual(self.get().status_code, 200)

    def test_borrowed_item_locked(self):
        Item.objects.filter(pk=self.item.pk).update(is_available=False)
        self.login()
        response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, BORROWED_MESSAGE, status_code=403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Kipas Angin Meja")

    def test_soft_deleted_item_is_404(self):
        self.item.soft_delete()
        self.login()
        self.assertEqual(self.get().status_code, 404)

    def test_put_not_allowed(self):
        self.login()
        self.assertEqual(self.client.put(self.url).status_code, 405)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post(self.url, valid_data(name="Kipas Angin Berdiri"))
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Kipas Angin Meja")


@override_settings(CACHES=TEST_CACHES)
class ItemEditPageTest(ItemEditTestMixin, TestCase):
    """GET biasa: halaman form penuh (fallback tanpa JS). GET HTMX: isi dialog."""

    def test_full_page_with_prefilled_form(self):
        self.login()
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_form.html")
        self.assertTemplateUsed(response, "base.html")
        form = response.context["form"]
        self.assertIsInstance(form, ItemForm)
        self.assertEqual(form.instance, self.item)
        self.assertContains(response, 'value="Kipas Angin Meja"')

    def test_full_page_title_actions_and_cancel(self):
        self.login()
        response = self.get()
        self.assertContains(response, "<title>Edit Barang — ShareSpace</title>", html=True)
        self.assertContains(response, f'action="{self.url}"')
        self.assertContains(response, f'hx-post="{self.url}"')
        self.assertContains(response, "Simpan Perubahan")
        self.assertContains(response, f'href="{self.detail_url}"')

    def test_htmx_get_returns_dialog_content_only(self):
        self.login()
        response = self.get(htmx=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/partials/item_edit_dialog.html")
        self.assertTemplateUsed(response, "items/partials/item_form.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, 'id="item-dialog-title"')
        self.assertContains(response, "Edit Barang")
        self.assertContains(response, 'id="item-form"')

    def test_dialog_has_close_controls(self):
        # Tombol tutup (×) dan link Batal; JS menutup dialog, tanpa JS link Batal kembali ke detail.
        self.login()
        response = self.get(htmx=True)
        self.assertContains(response, 'aria-label="Tutup dialog"')
        self.assertContains(response, "data-dialog-close", count=2)
        self.assertContains(response, f'href="{self.detail_url}"')

    def test_system_fields_not_rendered(self):
        self.login()
        response = self.get(htmx=True)
        for name in ["is_available", "is_verified", "is_deleted", "owner"]:
            self.assertNotContains(response, f'name="{name}"')


@override_settings(CACHES=TEST_CACHES)
class ItemEditSubmitTest(ItemEditTestMixin, TestCase):
    """Submit edit: field pemilik berubah, field sistem dan owner tidak."""

    def test_valid_post_updates_item_and_redirects(self):
        self.login()
        response = self.post()
        self.assertRedirects(response, self.detail_url)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Kipas Angin Berdiri")
        self.assertEqual(self.item.description, UPDATED_DESCRIPTION)
        self.assertEqual(self.item.category, Item.Category.OUTDOOR)

    def test_success_message_after_redirect(self):
        self.login()
        response = self.post(follow=True)
        messages = [str(m) for m in response.context["messages"]]
        self.assertEqual(messages, ["Perubahan pada Kipas Angin Berdiri berhasil disimpan."])

    def test_staff_edit_keeps_original_owner(self):
        self.login(self.staff)
        self.post()
        self.item.refresh_from_db()
        self.assertEqual(self.item.owner, self.owner)
        self.assertEqual(self.item.name, "Kipas Angin Berdiri")

    def test_system_fields_in_post_are_ignored(self):
        Item.objects.filter(pk=self.item.pk).update(is_verified=True)
        self.login()
        self.post(valid_data(owner=self.other.pk, is_available="False", is_verified="False", is_deleted="True"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.owner, self.owner)
        self.assertTrue(self.item.is_available)
        self.assertTrue(self.item.is_verified)
        self.assertFalse(self.item.is_deleted)

    def test_invalid_post_shows_full_page_and_keeps_item(self):
        self.login()
        response = self.post(valid_data(name="ab"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_form.html")
        self.assertIn("name", response.context["form"].errors)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Kipas Angin Meja")

    def test_htmx_invalid_post_returns_form_partial(self):
        self.login()
        response = self.post(valid_data(description="pendek"), htmx=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/partials/item_form.html")
        self.assertTemplateNotUsed(response, "items/partials/item_edit_dialog.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, 'class="form-error"')
        # Masih di dalam dialog: tombol batal tetap menutup dialog.
        self.assertContains(response, "data-dialog-close")

    def test_htmx_valid_post_swaps_detail_without_reload(self):
        self.login()
        response = self.post(htmx=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Retarget"], "#item-detail")
        self.assertEqual(response["HX-Reswap"], "outerHTML")
        self.assertTemplateUsed(response, "items/partials/item_detail_updated.html")
        self.assertTemplateUsed(response, "items/partials/item_detail_body.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, 'id="item-detail"')
        self.assertContains(response, "Kipas Angin Berdiri")
        self.assertContains(response, "<title>Kipas Angin Berdiri — ShareSpace</title>", html=True)

    def test_htmx_valid_post_triggers_toast_and_closes_dialog(self):
        self.login()
        response = self.post(htmx=True)
        trigger = json.loads(response["HX-Trigger"])
        self.assertEqual(trigger["showToast"], {
            "message": "Perubahan pada Kipas Angin Berdiri berhasil disimpan.",
            "level": "success",
        })
        self.assertIn("closeItemDialog", trigger)
        # Toast sudah lewat HX-Trigger; jangan antre lagi di Django messages (bisa tampil dua kali).
        self.assertEqual(list(get_messages(response.wsgi_request)), [])

    def test_htmx_updated_detail_keeps_manage_buttons(self):
        self.login()
        response = self.post(htmx=True)
        self.assertContains(response, f'hx-get="{self.url}"')

    def test_user_input_escaped_in_updated_detail(self):
        self.login()
        response = self.post(valid_data(name="<b>Kipas</b>", description=UPDATED_DESCRIPTION), htmx=True)
        self.assertNotContains(response, "<b>Kipas</b>")
        self.assertContains(response, "&lt;b&gt;Kipas&lt;/b&gt;")


@override_settings(CACHES=TEST_CACHES)
class ItemEditFromOtherPageTest(ItemEditTestMixin, TestCase):
    """Form HTMX di luar dialog detail (mis. halaman edit penuh): tidak ada #item-detail untuk di-swap."""

    def post_from(self, path, data=None):
        headers = {**HTMX_HEADERS, "HX-Current-URL": f"http://testserver{path}"}
        if data is None:
            data = valid_data(name="Kipas Angin Berdiri", description=UPDATED_DESCRIPTION)
        return self.client.post(self.url, data, headers=headers)

    def setUp(self):
        super().setUp()
        self.login()

    def test_from_full_edit_page_redirects_to_detail(self):
        response = self.post_from(self.url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], self.detail_url)
        self.assertNotIn("HX-Retarget", response)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Kipas Angin Berdiri")

    def test_from_full_edit_page_message_shown_after_redirect(self):
        response = self.post_from(self.url)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages, ["Perubahan pada Kipas Angin Berdiri berhasil disimpan."])

    def test_from_my_items_page_redirects_to_detail(self):
        response = self.post_from(f'{reverse("items:my_items")}?category=electronics')
        self.assertEqual(response["HX-Redirect"], self.detail_url)

    def test_from_detail_page_still_swaps_in_place(self):
        response = self.post_from(f"{self.detail_url}?ref=katalog")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Retarget"], "#item-detail")
        self.assertNotIn("HX-Redirect", response)

    def test_invalid_post_from_full_page_still_returns_form_partial(self):
        response = self.post_from(self.url, valid_data(name="ab"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/partials/item_form.html")
        self.assertNotIn("HX-Redirect", response)


@override_settings(CACHES=TEST_CACHES)
class ItemEditRateLimitTest(ItemEditTestMixin, TestCase):
    """Rate limit edit: ITEM_UPDATE_RATE_LIMIT POST per jam per user, terpisah dari create."""

    def test_limit_value(self):
        self.assertEqual(ITEM_UPDATE_RATE_LIMIT, 30)

    def exhaust(self):
        for _ in range(ITEM_UPDATE_RATE_LIMIT):
            self.assertEqual(self.post({}).status_code, 200)

    def test_post_over_limit_is_429(self):
        self.login()
        self.exhaust()
        response = self.post()
        self.assertEqual(response.status_code, 429)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Kipas Angin Meja")

    def test_htmx_over_limit_gets_toast(self):
        self.login()
        self.exhaust()
        response = self.post(htmx=True)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Terlalu banyak permintaan", self.toast(response)["message"])

    def test_scope_separate_from_create(self):
        self.login()
        create_url = reverse("items:create")
        for _ in range(ITEM_CREATE_RATE_LIMIT):
            self.post({}, url=create_url)
        self.assertEqual(self.post(url=create_url).status_code, 429)
        self.assertEqual(self.post().status_code, 302)


@override_settings(CACHES=TEST_CACHES)
class ItemDetailEditDialogTest(ItemEditTestMixin, TestCase):
    """Halaman detail (URL asli): tombol edit membuka dialog lewat HTMX, tetap jadi link biasa tanpa JS."""

    def get_detail(self, user=None):
        if user is not None:
            self.login(user)
        return self.client.get(self.detail_url)

    def test_detail_body_wrapped_for_swap(self):
        response = self.get_detail()
        self.assertTemplateUsed(response, "items/partials/item_detail_body.html")
        self.assertContains(response, 'id="item-detail"')

    def test_owner_edit_button_loads_dialog(self):
        response = self.get_detail(self.owner)
        self.assertContains(response, f'href="{self.url}"')
        self.assertContains(response, f'hx-get="{self.url}"')
        self.assertContains(response, 'hx-target="#item-dialog-body"')
        self.assertContains(response, 'id="item-dialog"')
        self.assertContains(response, 'aria-labelledby="item-dialog-title"')
        self.assertContains(response, "items/js/item-dialog.js")

    def test_staff_gets_dialog(self):
        response = self.get_detail(self.staff)
        self.assertContains(response, 'id="item-dialog"')

    def test_other_user_and_anonymous_get_no_dialog(self):
        for user in (None, self.other):
            with self.subTest(user=user):
                self.client.logout()
                response = self.get_detail(user)
                self.assertNotContains(response, 'id="item-dialog"')
                self.assertNotContains(response, "items/js/item-dialog.js")
                self.assertNotContains(response, f'hx-get="{self.url}"')

    def test_borrowed_item_has_no_dialog(self):
        Item.objects.filter(pk=self.item.pk).update(is_available=False)
        response = self.get_detail(self.owner)
        self.assertNotContains(response, 'id="item-dialog"')
        self.assertNotContains(response, f'hx-get="{self.url}"')
