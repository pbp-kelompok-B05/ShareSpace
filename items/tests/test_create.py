import json

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from items.forms import ItemForm
from items.models import Item
from items.tests.test_decorators import TEST_CACHES
from items.tests.test_models import VALID_DESCRIPTION, ItemTestMixin
from items.views import ITEM_CREATE_RATE_LIMIT

User = get_user_model()

HTMX_HEADERS = {"HX-Request": "true"}
FORM_FIELDS = ["name", "description", "category", "condition", "image_url"]


def valid_data(**overrides):
    data = {
        "name": "Tenda Dome 4 Orang",
        "description": "Tenda dome kapasitas empat orang, lengkap dengan frame dan pasak.",
        "category": Item.Category.OUTDOOR,
        "condition": Item.Condition.GOOD,
        "image_url": "",
    }
    data.update(overrides)
    return data


class ItemFormTest(ItemTestMixin, TestCase):
    """ItemForm: hanya field milik pemilik, label bahasa Indonesia, validasi mengikuti model."""

    def test_fields_exclude_system_fields(self):
        self.assertEqual(list(ItemForm().fields), FORM_FIELDS)

    def test_valid_data_without_owner(self):
        form = ItemForm(data=valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save(commit=False)
        self.assertIsNone(item.owner_id)
        self.assertTrue(item.is_available)

    def test_labels_in_indonesian(self):
        form = ItemForm()
        self.assertEqual(form.fields["name"].label, "Nama barang")
        self.assertEqual(form.fields["description"].label, "Deskripsi")
        self.assertEqual(form.fields["category"].label, "Kategori")
        self.assertEqual(form.fields["condition"].label, "Kondisi")
        self.assertEqual(form.fields["image_url"].label, "URL foto")

    def test_required_flags(self):
        form = ItemForm()
        for name in ["name", "description", "category", "condition"]:
            self.assertTrue(form.fields[name].required, name)
        self.assertFalse(form.fields["image_url"].required)

    def test_html_length_attributes_match_model_limits(self):
        form = ItemForm()
        self.assertEqual(form.fields["name"].widget.attrs["minlength"], "3")
        self.assertEqual(form.fields["name"].widget.attrs["maxlength"], "100")
        self.assertEqual(form.fields["description"].widget.attrs["minlength"], "20")
        self.assertEqual(form.fields["description"].widget.attrs["maxlength"], "1000")
        self.assertEqual(form.fields["image_url"].widget.attrs["maxlength"], "500")

    def test_select_placeholders(self):
        form = ItemForm()
        self.assertEqual(form.fields["category"].choices[0], ("", "Pilih kategori"))
        self.assertEqual(form.fields["condition"].choices[0], ("", "Pilih kondisi"))
        self.assertEqual(form.fields["category"].choices[1:], Item.Category.choices)
        self.assertEqual(form.fields["condition"].choices[1:], Item.Condition.choices)

    def test_whitespace_is_stripped(self):
        form = ItemForm(data=valid_data(name="   Tenda Dome   ", description=f"  {VALID_DESCRIPTION}  "))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["name"], "Tenda Dome")
        self.assertEqual(form.cleaned_data["description"], VALID_DESCRIPTION)

    def assertInvalid(self, field, **overrides):
        form = ItemForm(data=valid_data(**overrides))
        self.assertFalse(form.is_valid())
        self.assertIn(field, form.errors)

    def test_name_limits(self):
        self.assertInvalid("name", name="ab")
        self.assertInvalid("name", name="   ab   ")
        self.assertInvalid("name", name="x" * 101)
        self.assertInvalid("name", name="")
        self.assertTrue(ItemForm(data=valid_data(name="abc")).is_valid())
        self.assertTrue(ItemForm(data=valid_data(name="x" * 100)).is_valid())

    def test_description_limits(self):
        self.assertInvalid("description", description="x" * 19)
        self.assertInvalid("description", description="x" * 1001)
        self.assertInvalid("description", description="")
        self.assertTrue(ItemForm(data=valid_data(description="x" * 20)).is_valid())
        self.assertTrue(ItemForm(data=valid_data(description="x" * 1000)).is_valid())

    def test_invalid_choices(self):
        self.assertInvalid("category", category="weapons")
        self.assertInvalid("category", category="")
        self.assertInvalid("condition", condition="broken")
        self.assertInvalid("condition", condition="")

    def test_image_url_only_http_or_https(self):
        self.assertInvalid("image_url", image_url="javascript:alert(1)")
        self.assertInvalid("image_url", image_url="ftp://example.com/foto.jpg")
        self.assertInvalid("image_url", image_url="bukan url")
        self.assertInvalid("image_url", image_url="https://example.com/" + "a" * 500)
        self.assertTrue(ItemForm(data=valid_data(image_url="http://example.com/a.jpg")).is_valid())
        self.assertTrue(ItemForm(data=valid_data(image_url="https://example.com/a.jpg")).is_valid())

    def test_image_url_without_scheme_assumes_https(self):
        form = ItemForm(data=valid_data(image_url="example.com/foto.jpg"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["image_url"], "https://example.com/foto.jpg")

    def test_first_error_field_gets_autofocus(self):
        # HTMX memfokus elemen ber-autofocus setelah swap, sehingga error langsung terbaca.
        form = ItemForm(data=valid_data(description="pendek", condition="broken"))
        self.assertFalse(form.is_valid())
        self.assertTrue(form.fields["description"].widget.attrs.get("autofocus"))
        self.assertNotIn("autofocus", form.fields["condition"].widget.attrs)
        self.assertNotIn("autofocus", form.fields["name"].widget.attrs)

    def test_valid_form_has_no_autofocus(self):
        form = ItemForm(data=valid_data())
        self.assertTrue(form.is_valid())
        for field in form.fields.values():
            self.assertNotIn("autofocus", field.widget.attrs)


class ItemCreateTestMixin(ItemTestMixin):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other = User.objects.create_user(username="itemtest_create_other")
        cls.staff = User.objects.create_user(username="itemtest_create_staff", is_staff=True)

    def setUp(self):
        # Counter rate limit disimpan di cache; jangan bocor antar test.
        cache.clear()
        self.url = reverse("items:create")

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def post(self, data=None, htmx=False, **kwargs):
        headers = HTMX_HEADERS if htmx else {}
        return self.client.post(self.url, data if data is not None else valid_data(), headers=headers, **kwargs)


@override_settings(CACHES=TEST_CACHES)
class ItemCreatePageTest(ItemCreateTestMixin, TestCase):
    """Halaman tambah barang: hanya untuk user login, form lengkap dan aksesibel."""

    def test_url(self):
        self.assertEqual(self.url, "/katalog/tambah/")

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("authentication:login")))
        self.assertIn("next=/katalog/tambah/", response.url)

    def test_anonymous_htmx_gets_hx_redirect(self):
        response = self.post(htmx=True)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(response["HX-Redirect"].startswith(reverse("authentication:login")))

    def test_anonymous_post_creates_nothing(self):
        before = Item.all_objects.count()
        self.post()
        self.assertEqual(Item.all_objects.count(), before)

    def test_logged_in_gets_full_page(self):
        self.login()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_form.html")
        self.assertTemplateUsed(response, "items/partials/item_form.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertIsInstance(response.context["form"], ItemForm)
        self.assertFalse(response.context["form"].is_bound)

    def test_page_title_and_heading(self):
        self.login()
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Pinjamkan Barang — ShareSpace</title>", html=True)
        self.assertContains(response, "Pinjamkan Barang</h1>")

    def test_form_posts_to_create_url_with_htmx_and_csrf(self):
        self.login()
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn(f'action="{self.url}"', content)
        self.assertIn(f'hx-post="{self.url}"', content)
        self.assertIn('method="post"', content)
        self.assertIn('name="csrfmiddlewaretoken"', content)

    def test_every_field_has_label(self):
        self.login()
        response = self.client.get(self.url)
        for name in FORM_FIELDS:
            self.assertContains(response, f'for="id_{name}"')
            self.assertContains(response, f'id="id_{name}"')

    def test_system_fields_not_rendered(self):
        self.login()
        response = self.client.get(self.url)
        for name in ["is_available", "is_verified", "is_deleted", "owner"]:
            self.assertNotContains(response, f'name="{name}"')

    def test_cancel_link_back_to_catalog(self):
        self.login()
        response = self.client.get(self.url)
        self.assertContains(response, f'href="{reverse("items:catalog")}"')

    def test_put_not_allowed(self):
        self.login()
        self.assertEqual(self.client.put(self.url).status_code, 405)
        self.assertEqual(self.client.delete(self.url).status_code, 405)

    def test_catalog_shows_create_button(self):
        response = self.client.get(reverse("items:catalog"))
        self.assertContains(response, f'href="{self.url}"')
        self.assertContains(response, "+ Pinjamkan Barang")


@override_settings(CACHES=TEST_CACHES)
class ItemCreateSubmitTest(ItemCreateTestMixin, TestCase):
    """Submit form: barang dibuat milik user login; field sistem tidak bisa diisi dari luar."""

    def test_valid_post_creates_item_and_redirects_to_detail(self):
        self.login()
        response = self.post()
        item = Item.objects.get(owner=self.owner, name="Tenda Dome 4 Orang")
        self.assertRedirects(response, reverse("items:detail", args=[item.pk]))

    def test_created_item_owned_by_current_user(self):
        self.login(self.staff)
        self.post()
        item = Item.objects.get(name="Tenda Dome 4 Orang")
        self.assertEqual(item.owner, self.staff)

    def test_success_message_shown_on_detail(self):
        self.login()
        response = self.post(follow=True)
        messages = [str(m) for m in response.context["messages"]]
        self.assertEqual(messages, ["Tenda Dome 4 Orang berhasil ditambahkan ke katalog."])

    def test_system_fields_in_post_are_ignored(self):
        self.login()
        self.post(valid_data(
            owner=self.other.pk, is_available="False", is_verified="True",
            is_deleted="True", deleted_at="2026-01-01T00:00:00Z",
        ))
        item = Item.all_objects.get(name="Tenda Dome 4 Orang")
        self.assertEqual(item.owner, self.owner)
        self.assertTrue(item.is_available)
        self.assertFalse(item.is_verified)
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)

    def test_saved_values_are_stripped(self):
        self.login()
        self.post(valid_data(name="  Tenda Dome 4 Orang  "))
        self.assertTrue(Item.objects.filter(name="Tenda Dome 4 Orang").exists())

    def test_image_url_saved(self):
        self.login()
        self.post(valid_data(image_url="https://example.com/tenda.jpg"))
        item = Item.objects.get(name="Tenda Dome 4 Orang")
        self.assertEqual(item.image_url, "https://example.com/tenda.jpg")

    def test_htmx_valid_post_returns_hx_redirect(self):
        self.login()
        response = self.post(htmx=True)
        item = Item.objects.get(name="Tenda Dome 4 Orang")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], reverse("items:detail", args=[item.pk]))
        # Toast muncul di halaman detail lewat Django messages setelah HX-Redirect.
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages, ["Tenda Dome 4 Orang berhasil ditambahkan ke katalog."])

    def test_invalid_post_rerenders_full_page_with_errors(self):
        self.login()
        before = Item.all_objects.count()
        response = self.post(valid_data(name="ab"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Item.all_objects.count(), before)
        self.assertTemplateUsed(response, "items/item_form.html")
        self.assertIn("name", response.context["form"].errors)
        self.assertContains(response, 'class="form-error"')

    def test_htmx_invalid_post_returns_partial_only(self):
        self.login()
        response = self.post(valid_data(description="pendek"), htmx=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/partials/item_form.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, 'id="item-form"')
        self.assertContains(response, "autofocus")

    def test_invalid_post_keeps_input_values(self):
        self.login()
        response = self.post(valid_data(description="pendek"))
        self.assertContains(response, 'value="Tenda Dome 4 Orang"')

    def test_user_input_is_escaped_when_rerendered(self):
        self.login()
        response = self.post(valid_data(name="<script>alert(1)</script>", description="pendek"), htmx=True)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_missing_fields_create_nothing(self):
        self.login()
        before = Item.all_objects.count()
        response = self.post({})
        self.assertEqual(Item.all_objects.count(), before)
        for name in ["name", "description", "category", "condition"]:
            self.assertIn(name, response.context["form"].errors)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        before = Item.all_objects.count()
        response = client.post(self.url, valid_data())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Item.all_objects.count(), before)


@override_settings(CACHES=TEST_CACHES)
class ItemCreateRateLimitTest(ItemCreateTestMixin, TestCase):
    """Rate limit create: maksimal ITEM_CREATE_RATE_LIMIT POST per jam per user."""

    def test_limit_value(self):
        self.assertEqual(ITEM_CREATE_RATE_LIMIT, 10)

    def exhaust(self):
        # POST tidak valid juga dihitung; tidak perlu membuat banyak barang.
        for _ in range(ITEM_CREATE_RATE_LIMIT):
            self.assertEqual(self.post({}).status_code, 200)

    def test_post_over_limit_is_429_and_creates_nothing(self):
        self.login()
        self.exhaust()
        before = Item.all_objects.count()
        response = self.post()
        self.assertEqual(response.status_code, 429)
        self.assertTemplateUsed(response, "items/rate_limited.html")
        self.assertIn("Retry-After", response)
        self.assertEqual(Item.all_objects.count(), before)

    def test_htmx_over_limit_gets_toast(self):
        self.login()
        self.exhaust()
        response = self.post(htmx=True)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Terlalu banyak permintaan", json.loads(response["HX-Trigger"])["showToast"]["message"])

    def test_get_still_allowed_after_limit(self):
        self.login()
        self.exhaust()
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_limit_is_per_user(self):
        self.login()
        self.exhaust()
        self.login(self.other)
        self.assertEqual(self.post().status_code, 302)

    def test_anonymous_posts_not_counted_against_users(self):
        for _ in range(ITEM_CREATE_RATE_LIMIT + 1):
            self.post()
        self.login()
        self.assertEqual(self.post().status_code, 302)
