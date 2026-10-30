import datetime
from unittest.mock import MagicMock, patch
import requests

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from authentication.backends import GoogleAuthBackend, SSOUIAuthBackend
from django.contrib.admin.sites import AdminSite

from authentication.admin import LoginHelpRequestAdmin
from authentication.forms import LoginHelpRequestForm, UserProfileForm
from authentication.models import LoginHelpRequest, UserProfile
from authentication.views import (
    AdminModerationPermission,
    BaseProfileReputationProvider,
    ReviewModuleReputationProvider,
    UserDeletionValidator,
    reputation_service,
)
from items.models import Item
from loans.models import LoanRequest
from review.models import Report, Review


# Create your tests here.
class AuthenticationTest(TestCase):
    def setUp(self):
        self._orig_google_verify = GoogleAuthBackend.verify_token
        self._orig_sso_validate = SSOUIAuthBackend.validate_ticket
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
        GoogleAuthBackend.verify_token = self._orig_google_verify
        SSOUIAuthBackend.validate_ticket = self._orig_sso_validate

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

    def test_profile_renders_trust_score_and_reviews_empty(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trust Score")
        self.assertContains(response, "★ – / 5.0")
        self.assertContains(response, "Pengguna baru")
        self.assertContains(response, "Ulasan Komunitas (0)")
        self.assertContains(response, "Belum ada ulasan")

    def test_profile_renders_reviews_when_available(self):
        other_user = self.create_other_user()
        item = Item.objects.create(
            owner=self.user,
            name="Tenda Camping",
            description="Tenda dome kapasitas empat orang dalam kondisi bersih.",
            category=Item.Category.OUTDOOR,
            condition=Item.Condition.GOOD,
        )
        loan = LoanRequest.objects.create(
            borrower=other_user,
            item=item,
            start_date=datetime.date.today(),
            due_date=datetime.date.today() + datetime.timedelta(days=2),
            status=LoanRequest.Status.COMPLETED,
        )
        Review.objects.create(
            loan=loan,
            reviewer=other_user,
            reviewee=self.user,
            reviewer_role=Review.Role.BORROWER,
            rating=5,
            comment="Peminjam yang sangat bertanggung jawab, barang mulus.",
        )
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "★ 5.0 / 5.0")
        self.assertContains(response, "Ulasan Komunitas (1)")
        self.assertContains(response, "Fern Mage")
        self.assertContains(response, "Peminjam yang sangat bertanggung jawab, barang mulus.")
        self.assertContains(response, "Barang yang Sedang Dipinjamkan (1)")
        self.assertContains(response, "Tenda Camping")
        self.assertContains(response, "Tersedia")
        self.assertContains(response, "Barang Dipinjamkan")
        self.assertContains(response, "Barang Dipinjam")
        self.assertContains(response, "Transaksi Selesai")

    def test_public_profile_renders_trust_score_and_reviews(self):
        other_user = self.create_other_user()
        Item.objects.create(
            owner=other_user,
            name="Ransel Gunung 60L",
            description="Ransel kapasitas enam puluh liter cocok untuk hiking.",
            category=Item.Category.OUTDOOR,
            condition=Item.Condition.LIKE_NEW,
        )
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("authentication:public_profile", args=["fern"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trust Score")
        self.assertContains(response, "★ – / 5.0")
        self.assertContains(response, "Ulasan Komunitas (0)")
        self.assertContains(response, "Belum ada ulasan")
        self.assertContains(response, "Barang yang Sedang Dipinjamkan (1)")
        self.assertContains(response, "Ransel Gunung 60L")

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
        GoogleAuthBackend.verify_token = lambda self, token: {
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
        self.assertFalse(user.userprofile.is_verified)
        self.assertEqual(user.userprofile.auth_provider, UserProfile.AuthProvider.GOOGLE)
        self.assertEqual(user.userprofile.full_name, "Himmel The Hero")
        self.assertEqual(user.userprofile.profile_picture_url, "https://img.com/himmel.jpg")

    def test_google_login_json_success(self):
        GoogleAuthBackend.verify_token = lambda self, token: {
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
        GoogleAuthBackend.verify_token = lambda self, token: None

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
        SSOUIAuthBackend.validate_ticket = lambda self, ticket, service_url: {
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
        SSOUIAuthBackend.validate_ticket = lambda self, ticket, service_url: None

        response = self.client.get(
            reverse("authentication:sso_ui_callback") + "?ticket=ST-expired-ticket",
        )
        self.assertRedirects(response, reverse("authentication:login"))
        self.assertFalse(User.objects.filter(username="azka.nur").exists())

    def test_google_login_already_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("authentication:google_login"), {"credential": "dummy"})
        self.assertRedirects(response, reverse("landing_page"))

        response_json = self.client.post(
            reverse("authentication:google_login"),
            data='{"credential": "dummy"}',
            content_type="application/json",
        )
        self.assertEqual(response_json.status_code, 200)
        self.assertEqual(response_json.json()["status"], "success")

    def test_sso_ui_login_already_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("authentication:sso_ui_login"))
        self.assertRedirects(response, reverse("landing_page"))

    def test_sso_ui_callback_already_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("authentication:sso_ui_callback") + "?ticket=ST-expired-or-consumed")
        self.assertRedirects(response, reverse("landing_page"))


class AuthBackendsTest(TestCase):
    def test_sso_ui_parse_cas_xml_success(self):
        backend = SSOUIAuthBackend()
        cas_xml = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
            <cas:authenticationSuccess>
                <cas:user>azka.nur</cas:user>
                <cas:attributes>
                    <cas:nama>Azka Nur Jauhar</cas:nama>
                    <cas:npm>2506123456</cas:npm>
                </cas:attributes>
            </cas:authenticationSuccess>
        </cas:serviceResponse>"""
        user_info = backend.parse_cas_xml(cas_xml)
        self.assertEqual(user_info["username"], "azka.nur")
        self.assertEqual(user_info["npm"], "2506123456")
        self.assertEqual(user_info["nama"], "Azka Nur Jauhar")

    def test_sso_ui_parse_cas_xml_failure(self):
        backend = SSOUIAuthBackend()
        cas_xml = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
            <cas:authenticationFailure code="INVALID_TICKET">Ticket expired</cas:authenticationFailure>
        </cas:serviceResponse>"""
        self.assertIsNone(backend.parse_cas_xml(cas_xml))

    def test_auth_provider_get_or_create_user(self):
        backend = GoogleAuthBackend()
        user = backend.get_or_create_user(
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
        self.assertFalse(user.userprofile.is_verified)

    def test_sso_ui_get_login_url(self):
        backend = SSOUIAuthBackend()
        url = backend.get_login_url("http://example.com/callback")
        self.assertIn("sso.ui.ac.id/cas2/login", url)
        self.assertIn("service=http", url)

    def test_sso_ui_parse_cas_xml_syntax_error(self):
        backend = SSOUIAuthBackend()
        self.assertIsNone(backend.parse_cas_xml("<<<invalid xml"))

    def test_google_authenticate_empty_credential(self):
        backend = GoogleAuthBackend()
        self.assertIsNone(backend.authenticate(None, google_credential=""))

    def test_sso_ui_authenticate_empty_params(self):
        backend = SSOUIAuthBackend()
        self.assertIsNone(backend.authenticate(None, sso_ticket="", service_url=""))

    def test_auth_provider_username_collision(self):
        backend = GoogleAuthBackend()
        user1 = backend.get_or_create_user(
            username="claud",
            email="claud1@test.com",
            full_name="Claud One",
            auth_provider=UserProfile.AuthProvider.GOOGLE,
        )
        user2 = backend.get_or_create_user(
            username="claud",
            email="claud2@test.com",
            full_name="Claud Two",
            auth_provider=UserProfile.AuthProvider.GOOGLE,
        )
        self.assertEqual(user1.username, "claud")
        self.assertEqual(user2.username, "claud1")

    def test_auth_backend_get_user(self):
        backend = GoogleAuthBackend()
        user = backend.get_or_create_user(
            username="frieren_mage",
            email="frieren_mage@test.com",
            full_name="Frieren",
            auth_provider=UserProfile.AuthProvider.GOOGLE,
        )
        self.assertEqual(backend.get_user(user.id), user)
        self.assertIsNone(backend.get_user(999999))

    def test_sso_ui_parse_cas_xml_missing_username(self):
        backend = SSOUIAuthBackend()
        cas_xml = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
            <cas:authenticationSuccess>
                <cas:attributes>
                    <cas:nama>Tanpa Username</cas:nama>
                </cas:attributes>
            </cas:authenticationSuccess>
        </cas:serviceResponse>"""
        self.assertIsNone(backend.parse_cas_xml(cas_xml))

    def test_google_authenticate_unverified_email(self):
        backend = GoogleAuthBackend()
        backend.verify_token = lambda token: {"email": "test@gmail.com", "email_verified": False}
        self.assertIsNone(backend.authenticate(None, google_credential="unverified_token"))
    def test_google_verify_token_empty_client_id_fails_closed(self):
        backend = GoogleAuthBackend()
        with self.settings(GOOGLE_CLIENT_ID=""):
            self.assertIsNone(backend.verify_token("some_token"))

    def test_google_verify_token_wrong_audience_rejected(self):
        backend = GoogleAuthBackend()
        with self.settings(GOOGLE_CLIENT_ID="expected_client_id_123"):
            import unittest.mock as mock
            mock_response = mock.MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "aud": "wrong_other_app_client_id",
                "iss": "https://accounts.google.com",
                "email": "test@gmail.com",
                "email_verified": True,
            }
            with mock.patch("requests.get", return_value=mock_response):
                self.assertIsNone(backend.verify_token("fake_valid_token"))

    def test_google_verify_token_invalid_issuer_rejected(self):
        backend = GoogleAuthBackend()
        with self.settings(GOOGLE_CLIENT_ID="expected_client_id_123"):
            import unittest.mock as mock
            mock_response = mock.MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "aud": "expected_client_id_123",
                "iss": "https://evil-attacker.com",
                "email": "test@gmail.com",
                "email_verified": True,
            }
            with mock.patch("requests.get", return_value=mock_response):
                self.assertIsNone(backend.verify_token("fake_token"))

    def test_google_authenticate_deactivated_user_rejected(self):
        deactivated_user = User.objects.create_user(
            username="deactivated_user",
            email="deactivated@gmail.com",
            password="Password123.",
            is_active=False,
        )
        UserProfile.objects.create(user=deactivated_user)

        backend = GoogleAuthBackend()
        backend.verify_token = lambda token: {
            "email": "deactivated@gmail.com",
            "email_verified": True,
            "aud": getattr(settings, "GOOGLE_CLIENT_ID", ""),
            "iss": "https://accounts.google.com",
        }
        self.assertIsNone(backend.authenticate(None, google_credential="valid_token"))

    def test_sso_ui_authenticate_deactivated_user_rejected(self):
        deactivated_user = User.objects.create_user(
            username="deactivated_ui",
            email="deactivated_ui@ui.ac.id",
            password="Password123.",
            is_active=False,
        )
        UserProfile.objects.create(user=deactivated_user)

        backend = SSOUIAuthBackend()
        backend.validate_ticket = lambda ticket, service_url: {
            "username": "deactivated_ui",
            "nama": "Deactivated UI",
            "npm": "1234567890",
        }
        self.assertIsNone(backend.authenticate(None, sso_ticket="valid_ticket", service_url="http://testserver"))

    def test_get_user_deactivated_user_returns_none(self):
        deactivated_user = User.objects.create_user(
            username="inactive_target",
            email="inactive_target@test.com",
            password="Password123.",
            is_active=False,
        )
        backend = GoogleAuthBackend()
        self.assertIsNone(backend.get_user(deactivated_user.id))

    def test_google_auth_user_is_not_verified_by_default(self):
        backend = GoogleAuthBackend()
        user = backend.get_or_create_user(
            username="regular_google_user",
            email="regular_google_user@gmail.com",
            full_name="Regular Google",
            auth_provider=UserProfile.AuthProvider.GOOGLE,
            is_verified=False,
        )
        self.assertFalse(user.userprofile.is_verified)

    def test_google_authenticate_with_ui_email_is_verified(self):
        backend = GoogleAuthBackend()
        backend.verify_token = lambda token: {
            "email": "mahasiswa@ui.ac.id",
            "email_verified": True,
            "name": "Mahasiswa UI",
            "picture": "https://img.com/ui.png",
        }
        user = backend.authenticate(None, google_credential="mock_token")
        self.assertIsNotNone(user)
        self.assertTrue(user.userprofile.is_verified)

    def test_google_authenticate_with_office_ui_email_is_verified(self):
        backend = GoogleAuthBackend()
        backend.verify_token = lambda token: {
            "email": "dosen@office.ui.ac.id",
            "email_verified": True,
            "name": "Dosen UI",
            "picture": "https://img.com/office.png",
        }
        user = backend.authenticate(None, google_credential="mock_token")
        self.assertIsNotNone(user)
        self.assertTrue(user.userprofile.is_verified)

    def test_google_authenticate_with_regular_gmail_is_not_verified(self):
        backend = GoogleAuthBackend()
        backend.verify_token = lambda token: {
            "email": "umum@gmail.com",
            "email_verified": True,
            "name": "Pengguna Umum",
            "picture": "https://img.com/umum.png",
        }
        user = backend.authenticate(None, google_credential="mock_token")
        self.assertIsNotNone(user)
        self.assertFalse(user.userprofile.is_verified)

    def test_sso_ui_authenticate_with_inactive_local_user_with_same_username_allowed(self):
        deactivated_local = User.objects.create_user(
            username="student_ui",
            email="other@local.com",
            password="Password123.",
            is_active=False,
        )
        UserProfile.objects.create(user=deactivated_local)

        backend = SSOUIAuthBackend()
        backend.validate_ticket = lambda ticket, service_url: {
            "username": "student_ui",
            "nama": "Student UI Asli",
            "npm": "9876543210",
        }
        user = backend.authenticate(None, sso_ticket="valid_ticket", service_url="http://testserver")
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "student_ui@ui.ac.id")
        self.assertEqual(user.username, "student_ui1")
        self.assertTrue(user.is_active)

    def test_user_profile_db_defaults(self):
        from django.db import connection
        user = User.objects.create_user(username="db_default_test", password="Password123.")
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO authentication_userprofile (user_id, full_name, phone_number, address) VALUES (%s, %s, %s, %s)",
                [user.id, "DB Default User", "0812345", "Depok"],
            )
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.auth_provider, UserProfile.AuthProvider.LOCAL)
        self.assertFalse(profile.is_verified)
        self.assertEqual(profile.npm, "")


class ProfileReputationProviderTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test_rep_user", password="Password123.")
        self.other_user = User.objects.create_user(username="other_rep_user", password="Password123.")
        UserProfile.objects.create(user=self.user, full_name="Rep User")
        UserProfile.objects.create(user=self.other_user, full_name="Other Rep User")

    def test_base_provider_not_implemented(self):
        base = BaseProfileReputationProvider()
        with self.assertRaises(NotImplementedError):
            base.get_reputation_context(self.user)

    def test_provider_inheritance_and_polymorphism(self):
        provider = ReviewModuleReputationProvider()
        self.assertIsInstance(provider, BaseProfileReputationProvider)

    def test_provider_context_empty(self):
        ctx = reputation_service.get_reputation_context(self.user)
        self.assertEqual(ctx["reviews_count"], 0)
        self.assertIsNone(ctx["average_rating"])
        self.assertEqual(ctx["completed_loans_count"], 0)
        self.assertEqual(ctx["borrowed_loans_count"], 0)
        self.assertEqual(ctx["owned_items_count"], 0)
        self.assertIsNone(ctx["trust_score"])
        self.assertEqual(ctx["trust_level"], "Pengguna baru")
        self.assertEqual(len(ctx["reviews"]), 0)
        self.assertEqual(len(ctx["user_items"]), 0)

    def test_provider_context_with_loans_and_reviews(self):
        item = Item.objects.create(
            owner=self.user,
            name="Kamera DSLR",
            description="Kamera DSLR untuk fotografi pemula hingga pro.",
            category=Item.Category.ELECTRONICS,
            condition=Item.Condition.LIKE_NEW,
        )
        loan = LoanRequest.objects.create(
            borrower=self.other_user,
            item=item,
            start_date=datetime.date.today(),
            due_date=datetime.date.today() + datetime.timedelta(days=3),
            status=LoanRequest.Status.COMPLETED,
        )
        Review.objects.create(
            loan=loan,
            reviewer=self.other_user,
            reviewee=self.user,
            reviewer_role=Review.Role.BORROWER,
            rating=5,
            comment="Barang sangat bagus dan pemilik ramah!",
        )
        Report.objects.create(
            reporter=self.other_user,
            target_user=self.user,
            reason=Report.Reason.OTHER,
            description="Laporan pengetesan deskripsi minimal dua puluh karakter.",
            status=Report.Status.RESOLVED,
        )

        ctx = reputation_service.get_reputation_context(self.user)
        self.assertEqual(ctx["reviews_count"], 1)
        self.assertEqual(ctx["average_rating"], 5.0)
        self.assertEqual(ctx["completed_loans_count"], 1)
        self.assertEqual(ctx["owned_items_count"], 1)
        self.assertEqual(len(ctx["user_items"]), 1)
        self.assertEqual(ctx["borrowed_loans_count"], 0)
        self.assertIsNotNone(ctx["trust_score"])
        self.assertEqual(len(ctx["reviews"]), 1)
        self.assertEqual(ctx["reviews"][0].reviewer_initial, "O")
        self.assertEqual(ctx["reviews"][0].reviewer_display_name, "Other Rep User")
        self.assertTrue(len(ctx["reviews"][0].relative_time) > 0)


class ProfileReputationApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="api_user", password="Password123.")
        self.other_user = User.objects.create_user(username="other_api_user", password="Password123.")
        UserProfile.objects.create(user=self.user, full_name="API User")
        UserProfile.objects.create(user=self.other_user, full_name="Other API User")

    def test_api_redirect_anonymous(self):
        response = self.client.get(reverse("authentication:profile_reputation_api"))
        self.assertEqual(response.status_code, 302)

    def test_api_authenticated_own(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("authentication:profile_reputation_api"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["username"], "api_user")
        self.assertIn("trust_score", data)
        self.assertIn("reviews", data)
        self.assertIn("user_items", data)

    def test_api_public_user(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("authentication:public_profile_reputation_api", args=["other_api_user"])
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["username"], "other_api_user")

    def test_api_unknown_user_404(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("authentication:public_profile_reputation_api", args=["unknown_ghost"])
        )
        self.assertEqual(response.status_code, 404)

    def test_api_post_method_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("authentication:profile_reputation_api"))
        self.assertEqual(response.status_code, 405)

class LoginHelpRequestTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client_guest = self.client_class()
        self.help_url = reverse("authentication:login_help_request")
        self.existing_user = User.objects.create_user(
            username="frieren_lost",
            email="frieren_lost@example.com",
            password="Password123.",
        )

    def test_login_help_page_accessible_by_guest(self):
        """Tamu unauthenticated dapat mengakses halaman bantuan kendala login."""
        response = self.client_guest.get(self.help_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login_help_form.html")
        self.assertContains(response, "Bantuan Kendala Login")
        self.assertContains(response, "Catatan untuk Pengguna SSO UI &amp; Google:")

    def test_login_help_page_redirect_if_authenticated(self):
        """Pengguna yang sudah login dialihkan ke landing page saat mengakses form bantuan."""
        user = User.objects.create_user(username="already_logged_in_user", password="Password123.")
        self.client.force_login(user)
        response = self.client.get(self.help_url)
        self.assertRedirects(response, reverse("landing_page"))

    def test_login_help_submission_success(self):
        """Tamu dapat mengirimkan permohonan bantuan dan tersimpan dengan benar."""
        data = {
            "email_or_username": "frieren_lost",
            "contact_email": "frieren_contact@example.com",
            "issue_type": "forgot_password",
            "message": "Saya lupa kata sandi akun lokal saya, mohon bantuan reset.",
        }
        response = self.client_guest.post(self.help_url, data)
        self.assertRedirects(response, reverse("authentication:login"))

        req = LoginHelpRequest.objects.filter(email_or_username="frieren_lost").first()
        self.assertIsNotNone(req)
        self.assertEqual(req.contact_email, "frieren_contact@example.com")
        self.assertEqual(req.issue_type, LoginHelpRequest.IssueType.FORGOT_PASSWORD)
        self.assertEqual(req.status, LoginHelpRequest.Status.PENDING)
        self.assertIn("lupa kata sandi", req.message)

    def test_login_help_form_validation(self):
        """Form bantuan memvalidasi field yang wajib diisi."""
        form = LoginHelpRequestForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("email_or_username", form.errors)
        self.assertIn("contact_email", form.errors)
        self.assertIn("message", form.errors)

    def test_login_help_form_sanitization(self):
        """Form bantuan membersihkan tag HTML berbahaya."""
        User.objects.create_user(username="user_hack", password="Password123.")
        form = LoginHelpRequestForm(
            data={
                "email_or_username": "<b>user_hack</b>",
                "contact_email": "hack@example.com",
                "issue_type": "other",
                "message": "<script>alert('xss')</script>Butuh bantuan login.",
            }
        )
        self.assertTrue(form.is_valid())
        cleaned = form.save(commit=False)
        self.assertEqual(cleaned.email_or_username, "user_hack")
        self.assertEqual(cleaned.message, "alert('xss')Butuh bantuan login.")

    def test_login_help_admin_mark_as_resolved(self):
        """Admin action mark_as_resolved mengubah status permohonan menjadi resolved."""
        req = LoginHelpRequest.objects.create(
            email_or_username="stark",
            contact_email="stark@example.com",
            issue_type=LoginHelpRequest.IssueType.ACCOUNT_LOCKED,
            message="Akun saya dinonaktifkan.",
            status=LoginHelpRequest.Status.PENDING,
        )
        admin = LoginHelpRequestAdmin(LoginHelpRequest, AdminSite())
        qs = LoginHelpRequest.objects.filter(pk=req.pk)

        class DummyRequest:
            def __init__(self):
                self._messages = []

        dummy_req = DummyRequest()
        admin.message_user = lambda request, msg: dummy_req._messages.append(msg)
        admin.mark_as_resolved(dummy_req, qs)

        req.refresh_from_db()
        self.assertEqual(req.status, LoginHelpRequest.Status.RESOLVED)

    def test_login_help_submission_prevents_user_enumeration(self):
        """Form bantuan tidak membocorkan apakah username/email terdaftar (mencegah user enumeration)."""
        data = {
            "email_or_username": "akun_hantu_yang_tidak_ada",
            "contact_email": "kontak@example.com",
            "issue_type": "forgot_password",
            "message": "Saya lupa kata sandi akun saya yang tidak ada.",
        }
        response = self.client_guest.post(self.help_url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jika akun terdaftar, admin akan menghubungi email kontakmu")
        req = LoginHelpRequest.objects.filter(email_or_username="akun_hantu_yang_tidak_ada").first()
        self.assertIsNotNone(req)

    def test_login_help_rate_limiting(self):
        """Pengiriman form bantuan dibatasi oleh rate limit (maksimal 5 kali per menit)."""
        data = {
            "email_or_username": "frieren_lost",
            "contact_email": "frieren_contact@example.com",
            "issue_type": "forgot_password",
            "message": "Saya lupa kata sandi akun lokal saya.",
        }
        for _ in range(5):
            res = self.client_guest.post(self.help_url, data)
            self.assertRedirects(res, reverse("authentication:login"))

        blocked = self.client_guest.post(self.help_url, data)
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Terlalu banyak permintaan", blocked.content.decode())

    def test_login_page_contains_help_link(self):
        """Halaman login menyediakan tautan bantuan untuk kendala lupa password."""
        response = self.client.get(reverse("authentication:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.help_url)
        self.assertContains(response, "Hubungi Bantuan Admin")


class AdminModerationActionsTest(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="admin_staff", password="AdminPassword123.", is_staff=True
        )
        self.normal_user = User.objects.create_user(
            username="normal_user", password="UserPassword123.", is_staff=False
        )
        self.target_user = User.objects.create_user(
            username="target_user", password="TargetPassword123.", is_staff=False
        )
        self.superuser = User.objects.create_superuser(
            username="super_admin", password="SuperPassword123.", email="super@example.com"
        )
        self.other_staff = User.objects.create_user(
            username="other_staff", password="OtherStaffPass123.", is_staff=True
        )
        self.staff_profile = UserProfile.objects.create(user=self.staff_user, full_name="Admin Staff")
        self.normal_profile = UserProfile.objects.create(user=self.normal_user, full_name="Normal User")
        self.target_profile = UserProfile.objects.create(user=self.target_user, full_name="Target User")
        self.superuser_profile = UserProfile.objects.create(user=self.superuser, full_name="Super Admin")
        self.other_staff_profile = UserProfile.objects.create(user=self.other_staff, full_name="Other Staff")

    def test_non_staff_cannot_toggle_verify(self):
        """Pengguna non-staff dilarang mengubah status verifikasi (403 Forbidden)."""
        self.client.force_login(self.normal_user)
        response = self.client.post(
            reverse("authentication:admin_toggle_verify", args=[self.target_user.username])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_toggle_verify(self):
        """Tamu unauthenticated dialihkan ke halaman login saat mencoba aksi admin."""
        response = self.client.post(
            reverse("authentication:admin_toggle_verify", args=[self.target_user.username])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("authentication:login"), response.url)

    def test_non_staff_cannot_toggle_active(self):
        """Pengguna non-staff dilarang mengubah status aktif (403 Forbidden)."""
        self.client.force_login(self.normal_user)
        response = self.client.post(
            reverse("authentication:admin_toggle_active", args=[self.target_user.username])
        )
        self.assertEqual(response.status_code, 403)

    def test_non_staff_cannot_delete_user(self):
        """Pengguna non-staff dilarang menghapus akun pengguna (403 Forbidden)."""
        self.client.force_login(self.normal_user)
        response = self.client.post(
            reverse("authentication:admin_delete_user", args=[self.target_user.username])
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_can_toggle_verify(self):
        """Staf berhasil mengubah status verifikasi pengguna lain."""
        self.client.force_login(self.staff_user)
        self.assertFalse(self.target_profile.is_verified)

        # Toggle jadi True
        response = self.client.post(
            reverse("authentication:admin_toggle_verify", args=[self.target_user.username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.target_profile.refresh_from_db()
        self.assertTrue(self.target_profile.is_verified)

        # Toggle kembali jadi False
        response = self.client.post(
            reverse("authentication:admin_toggle_verify", args=[self.target_user.username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.target_profile.refresh_from_db()
        self.assertFalse(self.target_profile.is_verified)

    def test_staff_can_toggle_active(self):
        """Staf berhasil mengubah status aktif pengguna lain."""
        self.client.force_login(self.staff_user)
        self.assertTrue(self.target_user.is_active)

        # Deaktivasi
        response = self.client.post(
            reverse("authentication:admin_toggle_active", args=[self.target_user.username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_active)

        # Aktivasi kembali
        response = self.client.post(
            reverse("authentication:admin_toggle_active", args=[self.target_user.username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_active)

    def test_staff_cannot_deactivate_self(self):
        """Staf tidak dapat menonaktifkan akun staf miliknya sendiri."""
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("authentication:admin_toggle_active", args=[self.staff_user.username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.staff_user.refresh_from_db()
        self.assertTrue(self.staff_user.is_active)

    def test_staff_cannot_delete_self(self):
        """Staf tidak dapat menghapus akun miliknya sendiri."""
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("authentication:admin_delete_user", args=[self.staff_user.username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.staff_user.pk).exists())

    def test_staff_cannot_delete_user_with_active_loans(self):
        """Penghapusan user ditolak jika memiliki transaksi peminjaman aktif."""
        self.client.force_login(self.staff_user)
        item = Item.objects.create(
            owner=self.staff_user,
            name="Kamera DSLR",
            description="Kamera DSLR untuk dipinjam.",
            category=Item.Category.ELECTRONICS,
            condition=Item.Condition.GOOD,
        )
        LoanRequest.objects.create(
            borrower=self.target_user,
            item=item,
            start_date=datetime.date.today(),
            due_date=datetime.date.today() + datetime.timedelta(days=2),
            status=LoanRequest.Status.APPROVED,
        )

        response = self.client.post(
            reverse("authentication:admin_delete_user", args=[self.target_user.username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.target_user.pk).exists())

    def test_staff_cannot_delete_user_with_active_items(self):
        """Penghapusan user ditolak jika pengguna masih memiliki barang aktif di katalog."""
        self.client.force_login(self.staff_user)
        Item.objects.create(
            owner=self.target_user,
            name="Tenda Dome Camping",
            description="Tenda camping kapasitas 4 orang.",
            category=Item.Category.OUTDOOR,
            condition=Item.Condition.LIKE_NEW,
            is_deleted=False,
        )

        response = self.client.post(
            reverse("authentication:admin_delete_user", args=[self.target_user.username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.target_user.pk).exists())

    def test_staff_cannot_delete_user_with_active_reports(self):
        """Penghapusan user ditolak jika pengguna terlibat dalam laporan yang sedang aktif."""
        self.client.force_login(self.staff_user)
        Report.objects.create(
            reporter=self.staff_user,
            target_user=self.target_user,
            reason=Report.Reason.MISCONDUCT,
            description="Perilaku tidak sopan saat transaksi COD barang.",
            status=Report.Status.PENDING,
        )

        response = self.client.post(
            reverse("authentication:admin_delete_user", args=[self.target_user.username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.target_user.pk).exists())

    def test_staff_can_delete_clean_user(self):
        """Staf berhasil menghapus pengguna yang tidak memiliki transaksi atau relasi data aktif."""
        self.client.force_login(self.staff_user)
        target_username = self.target_user.username
        target_pk = self.target_user.pk

        response = self.client.post(
            reverse("authentication:admin_delete_user", args=[target_username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(pk=target_pk).exists())

    def test_staff_sees_moderation_panel_in_public_profile(self):
        """Staf melihat komponen Panel Moderasi Admin di profil publik pengguna lain."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("authentication:public_profile", args=[self.target_user.username])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel Moderasi Admin")
        self.assertContains(response, "Beri Verifikasi UI")
        self.assertContains(response, "Nonaktifkan Akun Ini")
        self.assertContains(response, "Kelola Lengkap di Django Admin")

    def test_non_staff_does_not_see_moderation_panel(self):
        """Pengguna non-staff tidak melihat Panel Moderasi Admin di profil publik."""
        self.client.force_login(self.normal_user)
        response = self.client.get(
            reverse("authentication:public_profile", args=[self.target_user.username])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Panel Moderasi Admin")
        self.assertNotContains(response, "Kelola Lengkap di Django Admin")

    def test_staff_can_view_inactive_user_public_profile(self):
        """Staf dapat melihat profil publik user yang dinonaktifkan untuk melakukan re-aktivasi."""
        self.target_user.is_active = False
        self.target_user.save()

        # Staff can view
        self.client.force_login(self.staff_user)
        staff_response = self.client.get(
            reverse("authentication:public_profile", args=[self.target_user.username])
        )
        self.assertEqual(staff_response.status_code, 200)
        self.assertContains(staff_response, "Aktifkan Kembali")

        # Non-staff receives 404
        self.client.force_login(self.normal_user)
        normal_response = self.client.get(
            reverse("authentication:public_profile", args=[self.target_user.username])
        )
        self.assertEqual(normal_response.status_code, 404)

    def test_staff_cannot_moderate_superuser(self):
        """Staf biasa dilarang memoderasi akun superuser (toggle verify, active, delete)."""
        self.client.force_login(self.staff_user)

        # 1. Toggle verify superuser ditolak
        verify_res = self.client.post(
            reverse("authentication:admin_toggle_verify", args=[self.superuser.username]),
            follow=True,
        )
        self.assertEqual(verify_res.status_code, 200)
        self.assertContains(verify_res, "Kamu tidak punya izin memoderasi akun admin.")
        self.superuser_profile.refresh_from_db()
        self.assertFalse(self.superuser_profile.is_verified)

        # 2. Toggle active superuser ditolak
        active_res = self.client.post(
            reverse("authentication:admin_toggle_active", args=[self.superuser.username]),
            follow=True,
        )
        self.assertEqual(active_res.status_code, 200)
        self.assertContains(active_res, "Kamu tidak punya izin memoderasi akun admin.")
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

        # 3. Delete superuser ditolak
        delete_res = self.client.post(
            reverse("authentication:admin_delete_user", args=[self.superuser.username]),
            follow=True,
        )
        self.assertEqual(delete_res.status_code, 200)
        self.assertContains(delete_res, "Kamu tidak punya izin memoderasi akun admin.")
        self.assertTrue(User.objects.filter(pk=self.superuser.pk).exists())

    def test_staff_cannot_moderate_other_staff(self):
        """Staf biasa dilarang memoderasi sesama akun staf."""
        self.client.force_login(self.staff_user)

        # Toggle verify staf lain ditolak
        res = self.client.post(
            reverse("authentication:admin_toggle_verify", args=[self.other_staff.username]),
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Kamu tidak punya izin memoderasi akun admin.")

        # Toggle active staf lain ditolak
        res = self.client.post(
            reverse("authentication:admin_toggle_active", args=[self.other_staff.username]),
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Kamu tidak punya izin memoderasi akun admin.")
        self.other_staff.refresh_from_db()
        self.assertTrue(self.other_staff.is_active)

        # Delete staf lain ditolak
        res = self.client.post(
            reverse("authentication:admin_delete_user", args=[self.other_staff.username]),
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Kamu tidak punya izin memoderasi akun admin.")
        self.assertTrue(User.objects.filter(pk=self.other_staff.pk).exists())

    def test_superuser_can_moderate_staff(self):
        """Superuser memiliki izin memoderasi akun staf (toggle verify dan toggle active)."""
        self.client.force_login(self.superuser)

        # Toggle verify staf berhasil
        res = self.client.post(
            reverse("authentication:admin_toggle_verify", args=[self.staff_user.username]),
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.staff_profile.refresh_from_db()
        self.assertTrue(self.staff_profile.is_verified)

        # Toggle active staf berhasil
        res = self.client.post(
            reverse("authentication:admin_toggle_active", args=[self.staff_user.username]),
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.staff_user.refresh_from_db()
        self.assertFalse(self.staff_user.is_active)

    def test_superuser_cannot_moderate_other_superuser(self):
        """Superuser tidak dapat memoderasi akun superuser lainnya melalui panel ini."""
        another_super = User.objects.create_superuser(
            username="another_super", password="AnotherSuperPass123.", email="super2@example.com"
        )
        self.client.force_login(self.superuser)

        res = self.client.post(
            reverse("authentication:admin_toggle_active", args=[another_super.username]),
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Kamu tidak punya izin memoderasi akun admin.")
        another_super.refresh_from_db()
        self.assertTrue(another_super.is_active)

    def test_moderation_panel_hidden_for_unauthorized_staff(self):
        """Panel Moderasi Admin disembunyikan saat staf melihat profil superuser atau sesama staf."""
        self.client.force_login(self.staff_user)

        # Staf melihat superuser -> panel tersembunyi
        super_res = self.client.get(
            reverse("authentication:public_profile", args=[self.superuser.username])
        )
        self.assertEqual(super_res.status_code, 200)
        self.assertNotContains(super_res, "Panel Moderasi Admin")

        # Staf melihat staf lain -> panel tersembunyi
        staff_res = self.client.get(
            reverse("authentication:public_profile", args=[self.other_staff.username])
        )
        self.assertEqual(staff_res.status_code, 200)
        self.assertNotContains(staff_res, "Panel Moderasi Admin")

        # Superuser melihat staf -> panel muncul
        self.client.force_login(self.superuser)
        view_staff_res = self.client.get(
            reverse("authentication:public_profile", args=[self.staff_user.username])
        )
        self.assertEqual(view_staff_res.status_code, 200)
        self.assertContains(view_staff_res, "Panel Moderasi Admin")

    def test_staff_cannot_delete_user_with_active_loan_report(self):
        """Penghapusan user ditolak jika user merupakan peminjam atau pemilik barang dalam transaksi yang dilaporkan."""
        self.client.force_login(self.staff_user)
        item = Item.objects.create(
            owner=self.staff_user,
            name="Proyektor Epson",
            description="Proyektor untuk presentasi.",
            category=Item.Category.ELECTRONICS,
            condition=Item.Condition.GOOD,
        )
        loan = LoanRequest.objects.create(
            borrower=self.target_user,
            item=item,
            start_date=datetime.date.today(),
            due_date=datetime.date.today() + datetime.timedelta(days=2),
            status=LoanRequest.Status.APPROVED,
        )
        Report.objects.create(
            reporter=self.staff_user,
            target_loan=loan,
            reason=Report.Reason.LATE_RETURN,
            description="Barang proyektor belum dikembalikan saat tanggal jatuh tempo.",
            status=Report.Status.PENDING,
        )

        reasons = UserDeletionValidator.get_blocking_reasons(self.target_user)
        self.assertIn("Pengguna masih terlibat dalam laporan yang sedang diproses.", reasons)

        response = self.client.post(
            reverse("authentication:admin_delete_user", args=[self.target_user.username]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.target_user.pk).exists())


class BackendsCoverageTest(TestCase):
    def test_get_user_invalid_id_type(self):
        backend = GoogleAuthBackend()
        self.assertIsNone(backend.get_user("bukan_angka_id"))

    def test_get_or_create_user_inactive_email(self):
        User.objects.create_user(username="inact_acc", email="inact@test.com", is_active=False)
        backend = GoogleAuthBackend()
        res = backend.get_or_create_user("inact_acc", "inact@test.com", "Inact", UserProfile.AuthProvider.GOOGLE)
        self.assertIsNone(res)

    def test_google_verify_token_status_not_200(self):
        backend = GoogleAuthBackend()
        with self.settings(GOOGLE_CLIENT_ID="valid_id"):
            mock_res = MagicMock(status_code=400)
            with patch("requests.get", return_value=mock_res):
                self.assertIsNone(backend.verify_token("bad_token"))

    def test_google_verify_token_request_exception(self):
        backend = GoogleAuthBackend()
        with self.settings(GOOGLE_CLIENT_ID="valid_id"):
            with patch("requests.get", side_effect=requests.RequestException("Network error")):
                self.assertIsNone(backend.verify_token("any_token"))

    def test_sso_ui_parse_cas_xml_type_error(self):
        backend = SSOUIAuthBackend()
        self.assertIsNone(backend.parse_cas_xml(None))

    def test_sso_ui_validate_ticket_non_200(self):
        backend = SSOUIAuthBackend()
        mock_res = MagicMock(status_code=500)
        with patch("requests.get", return_value=mock_res):
            self.assertIsNone(backend.validate_ticket("tkt", "http://service"))

    def test_sso_ui_validate_ticket_request_exception(self):
        backend = SSOUIAuthBackend()
        with patch("requests.get", side_effect=requests.RequestException("CAS error")):
            self.assertIsNone(backend.validate_ticket("tkt", "http://service"))

    def test_sso_ui_validate_ticket_success(self):
        backend = SSOUIAuthBackend()
        cas_xml = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
            <cas:authenticationSuccess>
                <cas:user>budi.santoso</cas:user>
                <cas:attributes>
                    <cas:nama>Budi Santoso</cas:nama>
                    <cas:npm>2506998877</cas:npm>
                </cas:attributes>
            </cas:authenticationSuccess>
        </cas:serviceResponse>"""
        mock_res = MagicMock(status_code=200, text=cas_xml)
        with patch("requests.get", return_value=mock_res):
            res = backend.validate_ticket("valid_tkt", "http://service")
            self.assertIsNotNone(res)
            self.assertEqual(res["username"], "budi.santoso")

