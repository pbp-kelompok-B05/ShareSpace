from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from authentication.forms import UserProfileForm
from authentication.models import UserProfile


# Create your tests here.
class AuthenticationTest(TestCase):
    def setUp(self):
        self.username = "frieren"
        self.password = "PasswordnyaFrieren69."
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            full_name="Frieren The Slayer",
            phone_number="081234567890",
            address="Depok Realm",
        )

    def test_login_page_accessible(self):
        response = self.client.get(reverse("authentication:login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login.html")

    def test_register_page_accessible(self):
        response = self.client.get(reverse("authentication:register"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "register.html")

    def test_login_success_and_cookie_set(self):
        response = self.client.post(
            reverse("authentication:login"),
            {
                "username": self.username,
                "password": self.password,
            },
        )
        self.assertRedirects(response, reverse("landing_page"))
        self.assertIn("last_login", response.cookies)

    def test_login_invalid_credentials(self):
        response = self.client.post(
            reverse("authentication:login"),
            {
                "username": self.username,
                "password": "PasswordnyaHimmel67.", # Password yang salah
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login.html")

    def test_logout_clears_cookie(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:logout"))
        self.assertRedirects(response, reverse("landing_page"))
        self.assertEqual(response.cookies["last_login"].value, "")

    def test_user_profile_str(self):
        self.assertEqual(str(self.profile), f"{self.username}'s Profile")

    def test_user_profile_form_valid(self):
        form = UserProfileForm(
            data={
                "full_name": "Fern",
                "phone_number": "08123456789",
                "address": "Kukusan, Depok",
                "profile_picture_url": "https://example.com/fern.jpg",
            }
        )
        self.assertTrue(form.is_valid())

    def test_user_profile_form_xss_sanitization(self):
        form = UserProfileForm(
            data={
                "full_name": "<b>Fern</b>",
                "phone_number": "08123456789",
                "address": "<i>Kukusan</i>, Depok",
                "profile_picture_url": "https://example.com/fern.jpg",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["full_name"], "Fern")
        self.assertEqual(form.cleaned_data["address"], "Kukusan, Depok")

    def test_user_profile_form_invalid_phone(self):
        form = UserProfileForm(
            data={
                "full_name": "Fern",
                "phone_number": "BUKAN_NOMOR_HP!@#",
                "address": "Kukusan, Depok",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("phone_number", form.errors)

    def test_user_profile_form_invalid_url(self):
        form = UserProfileForm(
            data={
                "full_name": "Fern",
                "phone_number": "08123456789",
                "address": "Kukusan, Depok",
                "profile_picture_url": "ftp://example.com/fern.jpg",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("profile_picture_url", form.errors)

    def test_profile_page_redirect_anonymous(self):
        response = self.client.get(reverse("authentication:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response.url)

    def test_profile_page_accessible_authenticated(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profile.html")
        self.assertContains(response, "Frieren The Slayer")

    def test_profile_page_htmx_partial(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(
            reverse("authentication:profile"),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profile_content.html")

    def test_edit_profile_redirect_anonymous(self):
        response = self.client.get(reverse("authentication:edit_profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response.url)

    def test_edit_profile_get_authenticated(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:edit_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_profile.html")

    def test_edit_profile_get_htmx_partial(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(
            reverse("authentication:edit_profile"),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_profile_content.html")

    def test_edit_profile_post_valid_redirects(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            reverse("authentication:edit_profile"),
            {
                "full_name": "Frieren Master",
                "phone_number": "089876543210",
                "address": "Kutek, Beji, Depok",
                "profile_picture_url": "https://example.com/frieren.png",
            },
        )
        self.assertRedirects(response, reverse("authentication:profile"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Frieren Master")

    def test_edit_profile_post_valid_htmx_returns_partial(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            reverse("authentication:edit_profile"),
            {
                "full_name": "Frieren Grand Mage",
                "phone_number": "089876543210",
                "address": "Kutek, Beji, Depok",
                "profile_picture_url": "https://example.com/frieren.png",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profile_content.html")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Frieren Grand Mage")

    def test_edit_profile_post_invalid(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            reverse("authentication:edit_profile"),
            {
                "full_name": "Frieren",
                "phone_number": "BUKAN_NOMOR_HP!@#",
                "address": "Depok",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_profile.html")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Frieren The Slayer")

    def test_deactivate_account_anonymous_redirect(self):
        response = self.client.get(reverse("authentication:deactivate_account"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response.url)

    def test_deactivate_account_get_authenticated(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:deactivate_account"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "deactivate_account.html")
        self.assertContains(response, self.username)

    def test_deactivate_account_post_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(reverse("authentication:deactivate_account"))
        self.assertRedirects(response, reverse("landing_page"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_deactivated_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        login_success = self.client.login(username=self.username, password=self.password)
        self.assertFalse(login_success)

    def test_profile_page_has_deactivate_link(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:profile"))
        self.assertContains(response, reverse("authentication:deactivate_account"))

    def test_profile_page_has_no_dummy_metrics(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:profile"))
        self.assertNotContains(response, "Rp 1,45 Jt")
        self.assertNotContains(response, "18.4 kg")

    def test_edit_profile_htmx_success_sends_toast_header(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            reverse("authentication:edit_profile"),
            {
                "full_name": "Frieren Grand Mage",
                "phone_number": "089876543210",
                "address": "Kutek, Beji, Depok",
                "profile_picture_url": "https://example.com/frieren.png",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertIn("showToast", response["HX-Trigger"])

    def create_other_user(self):
        other_user = User.objects.create_user(
            username="fern",
            password="PasswordnyaFern69.",
        )
        UserProfile.objects.create(
            user=other_user,
            full_name="Fern Mage",
            phone_number="089999999999",
            address="Rahasia Street",
        )
        return other_user

    def test_public_profile_redirect_anonymous(self):
        self.create_other_user()
        response = self.client.get(reverse("authentication:public_profile", args=["fern"]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response.url)

    def test_public_profile_shows_other_user(self):
        self.create_other_user()
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:public_profile", args=["fern"]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "public_profile.html")
        self.assertContains(response, "Fern Mage")

    def test_public_profile_hides_private_contact(self):
        self.create_other_user()
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:public_profile", args=["fern"]))
        self.assertNotContains(response, "089999999999")
        self.assertNotContains(response, "Rahasia Street")

    def test_public_profile_has_report_link(self):
        self.create_other_user()
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:public_profile", args=["fern"]))
        self.assertContains(response, reverse("review:report_user_create", args=["fern"]))

    def test_public_profile_own_username_redirects_to_profile(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:public_profile", args=[self.username]))
        self.assertRedirects(response, reverse("authentication:profile"))

    def test_public_profile_user_without_profile_row(self):
        User.objects.create_user(username="ghost", password="PasswordnyaGhost69.")
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:public_profile", args=["ghost"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ghost")

    def test_public_profile_unknown_user_returns_404(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:public_profile", args=["tidakada"]))
        self.assertEqual(response.status_code, 404)

    def test_public_profile_inactive_user_returns_404(self):
        other_user = self.create_other_user()
        other_user.is_active = False
        other_user.save()
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:public_profile", args=["fern"]))
        self.assertEqual(response.status_code, 404)


