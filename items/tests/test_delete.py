import json

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from items.models import Item
from items.tests.test_decorators import BORROWED_MESSAGE, FORBIDDEN_MESSAGE
from items.tests.test_models import ItemTestMixin

User = get_user_model()

HTMX_HEADERS = {"HX-Request": "true"}
SUCCESS_MESSAGE = "Kipas Angin Meja berhasil dihapus dari katalog."


class ItemDeleteTestMixin(ItemTestMixin):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other = User.objects.create_user(username="itemtest_delete_other")
        cls.staff = User.objects.create_user(username="itemtest_delete_staff", is_staff=True)

    def setUp(self):
        self.item = self.make_item()
        self.url = reverse("items:delete", args=[self.item.pk])
        self.detail_url = reverse("items:detail", args=[self.item.pk])

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def get(self, htmx=False):
        return self.client.get(self.url, headers=HTMX_HEADERS if htmx else {})

    def post(self, htmx=False, **kwargs):
        return self.client.post(self.url, headers=HTMX_HEADERS if htmx else {}, **kwargs)

    def assertNotDeleted(self):
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_deleted)
        self.assertIsNone(self.item.deleted_at)

    def assertSoftDeleted(self):
        # Baris tetap ada (FK loans memakai PROTECT dan riwayat harus utuh), hanya disembunyikan.
        item = Item.all_objects.get(pk=self.item.pk)
        self.assertTrue(item.is_deleted)
        self.assertIsNotNone(item.deleted_at)
        self.assertFalse(Item.objects.filter(pk=self.item.pk).exists())
        return item


class ItemDeleteAccessTest(ItemDeleteTestMixin, TestCase):
    """Hanya pemilik atau admin yang bisa menghapus; barang dipinjam terkunci."""

    def test_url(self):
        self.assertEqual(self.url, f"/katalog/{self.item.pk}/hapus/")

    def test_anonymous_redirected_to_login(self):
        response = self.post()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("authentication:login")))
        self.assertNotDeleted()

    def test_anonymous_htmx_gets_hx_redirect(self):
        response = self.post(htmx=True)
        self.assertEqual(response.status_code, 204)
        self.assertIn("HX-Redirect", response)
        self.assertNotDeleted()

    def test_other_user_forbidden(self):
        self.login(self.other)
        response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, FORBIDDEN_MESSAGE, status_code=403)
        self.assertNotDeleted()

    def test_other_user_htmx_gets_toast(self):
        self.login(self.other)
        response = self.post(htmx=True)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response["HX-Trigger"])["showToast"]["message"], FORBIDDEN_MESSAGE)
        self.assertNotDeleted()

    def test_staff_can_delete_other_users_item(self):
        self.login(self.staff)
        self.post()
        item = self.assertSoftDeleted()
        self.assertEqual(item.owner, self.owner)

    def test_borrowed_item_cannot_be_deleted(self):
        Item.objects.filter(pk=self.item.pk).update(is_available=False)
        for user in (self.owner, self.staff):
            with self.subTest(user=user):
                self.login(user)
                response = self.post()
                self.assertEqual(response.status_code, 403)
                self.assertContains(response, BORROWED_MESSAGE, status_code=403)
                self.assertNotDeleted()

    def test_already_deleted_item_is_404(self):
        self.item.soft_delete()
        self.login()
        self.assertEqual(self.post().status_code, 404)
        self.assertEqual(self.get().status_code, 404)

    def test_put_and_delete_methods_not_allowed(self):
        self.login()
        self.assertEqual(self.client.put(self.url).status_code, 405)
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        self.assertNotDeleted()

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertNotDeleted()


class ItemDeleteConfirmTest(ItemDeleteTestMixin, TestCase):
    """GET hanya menampilkan konfirmasi: halaman penuh tanpa JS, isi dialog lewat HTMX."""

    def test_get_does_not_delete(self):
        self.login()
        self.get()
        self.get(htmx=True)
        self.assertNotDeleted()

    def test_full_confirmation_page(self):
        self.login()
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_confirm_delete.html")
        self.assertTemplateUsed(response, "items/partials/item_delete_form.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "<title>Hapus Barang — ShareSpace</title>", html=True)
        self.assertContains(response, "Kipas Angin Meja")
        self.assertContains(response, "disembunyikan dari katalog")

    def test_confirmation_form_posts_with_csrf(self):
        self.login()
        response = self.get()
        content = response.content.decode()
        self.assertIn(f'action="{self.url}"', content)
        self.assertIn(f'hx-post="{self.url}"', content)
        self.assertIn('method="post"', content)
        self.assertIn('name="csrfmiddlewaretoken"', content)
        self.assertContains(response, "Ya, hapus barang")
        self.assertContains(response, f'href="{self.detail_url}"')

    def test_htmx_get_returns_dialog_content_only(self):
        self.login()
        response = self.get(htmx=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/partials/item_delete_dialog.html")
        self.assertTemplateUsed(response, "items/partials/item_delete_form.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, 'id="item-dialog-title"')
        self.assertContains(response, "Hapus barang ini?")
        self.assertContains(response, 'aria-label="Tutup dialog"')
        self.assertContains(response, "data-dialog-close", count=2)

    def test_cancel_is_focused_first(self):
        # Aksi destruktif: fokus awal di Batal, bukan di tombol hapus.
        self.login()
        response = self.get(htmx=True)
        self.assertRegex(response.content.decode(), r'<a [^>]*data-dialog-close[^>]*autofocus')

    def test_item_name_escaped(self):
        Item.objects.filter(pk=self.item.pk).update(name="<b>Kipas</b>")
        self.login()
        response = self.get(htmx=True)
        self.assertNotContains(response, "<b>Kipas</b>")
        self.assertContains(response, "&lt;b&gt;Kipas&lt;/b&gt;")


class ItemDeleteSubmitTest(ItemDeleteTestMixin, TestCase):
    """POST: soft delete, lalu pemilik kembali ke "Barang saya" dengan pesan sukses."""

    def test_post_soft_deletes_and_redirects_owner_to_my_items(self):
        self.login()
        response = self.post()
        self.assertRedirects(response, reverse("items:my_items"))
        self.assertSoftDeleted()

    def test_staff_deleting_other_users_item_redirects_to_catalog(self):
        # "Barang saya" milik admin tidak berisi barang ini, jadi admin kembali ke katalog.
        self.login(self.staff)
        self.assertRedirects(self.post(), reverse("items:catalog"))

    def test_staff_deleting_other_users_item_htmx_redirects_to_catalog(self):
        self.login(self.staff)
        self.assertEqual(self.post(htmx=True)["HX-Redirect"], reverse("items:catalog"))

    def test_staff_deleting_own_item_redirects_to_my_items(self):
        own = self.make_item(owner=self.staff)
        self.login(self.staff)
        response = self.client.post(reverse("items:delete", args=[own.pk]))
        self.assertRedirects(response, reverse("items:my_items"))

    def test_deleted_item_listed_in_my_items_deleted_tab(self):
        self.login()
        response = self.post(follow=True)
        self.assertNotIn(self.item.name, [i.name for i in response.context["page_obj"].object_list])
        deleted_tab = self.client.get(reverse("items:my_items"), {"status": "deleted"})
        self.assertIn(self.item.name, [i.name for i in deleted_tab.context["page_obj"].object_list])

    def test_success_message(self):
        self.login()
        response = self.post(follow=True)
        self.assertEqual([str(m) for m in response.context["messages"]], [SUCCESS_MESSAGE])

    def test_deleted_item_gone_from_detail_and_catalog(self):
        self.login()
        self.post()
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)
        catalog = self.client.get(reverse("items:catalog"))
        self.assertNotIn(self.item, catalog.context["page_obj"].object_list)

    def test_htmx_post_returns_hx_redirect_with_message(self):
        self.login()
        response = self.post(htmx=True)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], reverse("items:my_items"))
        self.assertEqual([str(m) for m in get_messages(response.wsgi_request)], [SUCCESS_MESSAGE])
        self.assertSoftDeleted()

    def test_other_items_untouched(self):
        other_item = self.make_item(name="Barang Lain")
        self.login()
        self.post()
        other_item.refresh_from_db()
        self.assertFalse(other_item.is_deleted)


class ItemDetailDeleteButtonTest(ItemDeleteTestMixin, TestCase):
    """Tombol hapus di detail (URL asli): link biasa tanpa JS, dialog konfirmasi dengan HTMX."""

    def test_owner_delete_button_loads_dialog(self):
        self.login()
        response = self.client.get(self.detail_url)
        self.assertContains(response, f'href="{self.url}"')
        self.assertContains(response, f'hx-get="{self.url}"')

    def test_other_user_has_no_delete_button(self):
        self.login(self.other)
        response = self.client.get(self.detail_url)
        self.assertNotContains(response, f'href="{self.url}"')
        self.assertNotContains(response, "Hapus Barang")
