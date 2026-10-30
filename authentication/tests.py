import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from authentication.backends import GoogleAuthBackend, SSOUIAuthBackend
from authentication.forms import UserProfileForm
from authentication.models import UserProfile
from authentication.views import (
    BaseProfileReputationProvider,
    ReviewModuleReputationProvider,
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
        self.assertTrue(user.userprofile.is_verified)
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
        self.assertTrue(user.userprofile.is_verified)

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


