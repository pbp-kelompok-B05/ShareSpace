from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from authentication.forms import UserProfileForm
from authentication.models import UserProfile
from authentication.providers import GoogleAuthProvider, SSOUIAuthProvider


# Create your tests here.
class AuthenticationTest(TestCase):
    def setUp(self):
        self._orig_google_verify = GoogleAuthProvider.verify_token
        self._orig_sso_validate = SSOUIAuthProvider.validate_ticket
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

    def tearDown(self):
        GoogleAuthProvider.verify_token = self._orig_google_verify
        SSOUIAuthProvider.validate_ticket = self._orig_sso_validate

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

    def test_user_profile_defaults(self):
        self.assertEqual(self.profile.auth_provider, UserProfile.AuthProvider.LOCAL)
        self.assertFalse(self.profile.is_verified)
        self.assertEqual(self.profile.npm, "")
        self.assertFalse(self.profile.is_external_auth)

    def test_user_profile_external_auth_property(self):
        self.profile.auth_provider = UserProfile.AuthProvider.GOOGLE
        self.assertTrue(self.profile.is_external_auth)

        self.profile.auth_provider = UserProfile.AuthProvider.SSO_UI
        self.assertTrue(self.profile.is_external_auth)

        self.profile.auth_provider = UserProfile.AuthProvider.LOCAL
        self.assertFalse(self.profile.is_external_auth)

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

    def test_user_profile_form_valid_npm(self):
        form = UserProfileForm(
            data={
                "full_name": "Fern",
                "npm": "2506123456",
                "phone_number": "08123456789",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["npm"], "2506123456")

    def test_user_profile_form_invalid_npm(self):
        form = UserProfileForm(
            data={
                "full_name": "Fern",
                "npm": "2506ABCDEF",
                "phone_number": "08123456789",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("npm", form.errors)

    def test_user_profile_form_sso_ui_disabled_npm(self):
        self.profile.auth_provider = UserProfile.AuthProvider.SSO_UI
        self.profile.npm = "2506999999"
        self.profile.save()
        form = UserProfileForm(instance=self.profile)
        self.assertTrue(form.fields["npm"].disabled)

    def test_profile_page_redirect_anonymous(self):
        response = self.client.get(reverse("authentication:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response.url)

    def test_profile_page_accessible_authenticated(self):
        self.profile.is_verified = True
        self.profile.npm = "2506123456"
        self.profile.save()
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profile.html")
        self.assertContains(response, "Frieren The Slayer")
        self.assertContains(response, "✓ Terverifikasi")
        self.assertContains(response, "2506123456")
        self.assertContains(response, reverse("review:my_reports"))
        self.assertContains(response, "Laporan saya")

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
        self.assertEqual(response.headers.get("HX-Push-Url"), reverse("authentication:profile"))
        self.assertIn("showToast", response.headers.get("HX-Trigger", ""))
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

    def test_profile_page_has_my_reports_link(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:profile"))
        self.assertContains(response, reverse("review:my_reports"))

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

    def test_login_page_renders_external_auth_buttons(self):
        response = self.client.get(reverse("authentication:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Masuk dengan SSO UI")
        self.assertContains(response, "Masuk dengan Google")

    def test_register_page_renders_external_auth_buttons(self):
        response = self.client.get(reverse("authentication:register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daftar dengan SSO UI")
        self.assertContains(response, "Daftar dengan Google")

    def test_google_login_missing_credential(self):
        response = self.client.post(reverse("authentication:google_login"), {})
        self.assertRedirects(response, reverse("authentication:login"))

    def test_google_login_success(self):
        GoogleAuthProvider.verify_token = lambda self, token: {
            "email": "himmel@hero.com",
            "name": "Himmel The Hero",
            "email_verified": True,
            "picture": "https://img.com/himmel.jpg",
        }

        response = self.client.post(
            reverse("authentication:google_login"),
            {"credential": "valid_mock_token"},
        )
        self.assertRedirects(response, reverse("landing_page"))
        self.assertIn("last_login", response.cookies)

        user = User.objects.get(email="himmel@hero.com")
        self.assertEqual(user.username, "himmel")
        self.assertTrue(user.userprofile.is_verified)
        self.assertEqual(user.userprofile.auth_provider, UserProfile.AuthProvider.GOOGLE)
        self.assertEqual(user.userprofile.full_name, "Himmel The Hero")
        self.assertEqual(user.userprofile.profile_picture_url, "https://img.com/himmel.jpg")

    def test_google_login_json_success(self):
        GoogleAuthProvider.verify_token = lambda self, token: {
            "email": "eisen@dwarf.com",
            "name": "Eisen The Warrior",
            "email_verified": True,
            "picture": "https://img.com/eisen.jpg",
        }

        response = self.client.post(
            reverse("authentication:google_login"),
            {"credential": "valid_mock_token"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("last_login", response.cookies)
        self.assertTrue(User.objects.filter(email="eisen@dwarf.com").exists())

    def test_google_login_invalid_token(self):
        GoogleAuthProvider.verify_token = lambda self, token: None

        response = self.client.post(
            reverse("authentication:google_login"),
            {"credential": "invalid_mock_token"},
        )
        self.assertRedirects(response, reverse("authentication:login"))
        self.assertFalse(User.objects.filter(email="invalid@mock.com").exists())

    def test_sso_ui_login_redirect(self):
        response = self.client.get(reverse("authentication:sso_ui_login"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("sso.ui.ac.id/cas2/login", response.url)
        self.assertIn("service=", response.url)

    def test_sso_ui_callback_missing_ticket(self):
        response = self.client.get(reverse("authentication:sso_ui_callback"))
        self.assertRedirects(response, reverse("authentication:login"))

    def test_sso_ui_callback_success(self):
        SSOUIAuthProvider.validate_ticket = lambda self, ticket, service_url: {
            "username": "azka.nur",
            "nama": "Azka Nur Jauhar",
            "npm": "2506123456",
        }

        response = self.client.get(
            reverse("authentication:sso_ui_callback") + "?ticket=ST-123456-valid",
        )
        self.assertRedirects(response, reverse("landing_page"))
        self.assertIn("last_login", response.cookies)

        user = User.objects.get(username="azka.nur")
        self.assertEqual(user.email, "azka.nur@ui.ac.id")
        self.assertTrue(user.userprofile.is_verified)
        self.assertEqual(user.userprofile.auth_provider, UserProfile.AuthProvider.SSO_UI)
        self.assertEqual(user.userprofile.npm, "2506123456")
        self.assertEqual(user.userprofile.full_name, "Azka Nur Jauhar")

    def test_sso_ui_callback_failure(self):
        SSOUIAuthProvider.validate_ticket = lambda self, ticket, service_url: None

        response = self.client.get(
            reverse("authentication:sso_ui_callback") + "?ticket=ST-expired-ticket",
        )
        self.assertRedirects(response, reverse("authentication:login"))
        self.assertFalse(User.objects.filter(username="azka.nur").exists())


class AuthProvidersTest(TestCase):
    def test_sso_ui_parse_cas_xml_success(self):
        provider = SSOUIAuthProvider()
        cas_xml = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
            <cas:authenticationSuccess>
                <cas:user>azka.nur</cas:user>
                <cas:attributes>
                    <cas:nama>Azka Nur Jauhar</cas:nama>
                    <cas:npm>2506123456</cas:npm>
                </cas:attributes>
            </cas:authenticationSuccess>
        </cas:serviceResponse>"""
        user_info = provider.parse_cas_xml(cas_xml)
        self.assertEqual(user_info["username"], "azka.nur")
        self.assertEqual(user_info["npm"], "2506123456")
        self.assertEqual(user_info["nama"], "Azka Nur Jauhar")

    def test_sso_ui_parse_cas_xml_failure(self):
        provider = SSOUIAuthProvider()
        cas_xml = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
            <cas:authenticationFailure code="INVALID_TICKET">Ticket expired</cas:authenticationFailure>
        </cas:serviceResponse>"""
        self.assertIsNone(provider.parse_cas_xml(cas_xml))

    def test_auth_provider_get_or_create_user(self):
        provider = GoogleAuthProvider()
        user = provider.get_or_create_user(
            username="heiter",
            email="heiter@priest.com",
            full_name="Heiter The Priest",
            auth_provider=UserProfile.AuthProvider.GOOGLE,
            npm="",
            profile_picture_url="https://img.com/heiter.jpg",
        )
        self.assertEqual(user.username, "heiter")
        self.assertEqual(user.email, "heiter@priest.com")
        self.assertEqual(user.userprofile.full_name, "Heiter The Priest")
        self.assertEqual(user.userprofile.auth_provider, UserProfile.AuthProvider.GOOGLE)
        self.assertTrue(user.userprofile.is_verified)
    def test_sso_ui_get_login_url(self):
        provider = SSOUIAuthProvider()
        url = provider.get_login_url("http://example.com/callback")
        self.assertIn("sso.ui.ac.id/cas2/login", url)
        self.assertIn("service=http", url)

    def test_sso_ui_parse_cas_xml_syntax_error(self):
        provider = SSOUIAuthProvider()
        self.assertIsNone(provider.parse_cas_xml("<<<invalid xml"))

    def test_google_authenticate_empty_credential(self):
        provider = GoogleAuthProvider()
        self.assertIsNone(provider.authenticate(""))

    def test_sso_ui_authenticate_empty_params(self):
        provider = SSOUIAuthProvider()
        self.assertIsNone(provider.authenticate("", ""))

    def test_auth_provider_username_collision(self):
        provider = GoogleAuthProvider()
        user1 = provider.get_or_create_user(
            username="claud",
            email="claud1@test.com",
            full_name="Claud One",
            auth_provider=UserProfile.AuthProvider.GOOGLE,
        )
        user2 = provider.get_or_create_user(
            username="claud",
            email="claud2@test.com",
            full_name="Claud Two",
            auth_provider=UserProfile.AuthProvider.GOOGLE,
        )
        self.assertEqual(user1.username, "claud")
        self.assertEqual(user2.username, "claud1")
