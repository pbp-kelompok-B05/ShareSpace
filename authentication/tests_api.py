from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from authentication.models import LoginHelpRequest, UserProfile


class AuthenticationAPITest(APITestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.user = User.objects.create_user(
            username="azka",
            email="azka@ui.ac.id",
            password=self.password,
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            full_name="Azka Nur Jauhar",
            npm="2506612410",
            phone_number="081234567890",
            address="Kukusan, Beji, Depok",
            profile_picture_url="https://example.com/azka.jpg",
            auth_provider=UserProfile.AuthProvider.LOCAL,
            is_verified=False,
        )
        self.other_user = User.objects.create_user(
            username="frieren",
            email="frieren@example.com",
            password=self.password,
        )
        self.other_profile = UserProfile.objects.create(
            user=self.other_user,
            full_name="Frieren",
            phone_number="089999999999",
            address="Rahasia Pribadi",
        )
        self.inactive_user = User.objects.create_user(
            username="nonaktif",
            email="nonaktif@example.com",
            password=self.password,
            is_active=False,
        )
        self.inactive_profile = UserProfile.objects.create(
            user=self.inactive_user,
            full_name="User Nonaktif",
        )

        self.list_url = reverse("authentication_api:profile-list")
        self.me_url = reverse("authentication_api:profile-me")
        self.detail_url = reverse(
            "authentication_api:profile-detail", args=[self.other_user.username]
        )
        self.help_url = reverse("authentication_api:help-request-create")

    def test_profile_list_only_active_and_no_private_fields(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [item["username"] for item in response.data]
        self.assertIn("azka", usernames)
        self.assertIn("frieren", usernames)
        self.assertNotIn("nonaktif", usernames)
        for item in response.data:
            self.assertNotIn("phone_number", item)
            self.assertNotIn("address", item)
            self.assertNotIn("email", item)

        search_response = self.client.get(self.list_url, {"q": "azka"})
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(search_response.data), 1)
        self.assertEqual(search_response.data[0]["username"], "azka")

    def test_public_profile_detail_excludes_private_data_and_includes_reputation(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "frieren")
        self.assertEqual(response.data["full_name"], "Frieren")
        self.assertIn("auth_provider_display", response.data)
        self.assertIn("is_verified", response.data)
        self.assertIn("reputation", response.data)
        self.assertIn("trust_score", response.data["reputation"])
        self.assertIn("trust_level", response.data["reputation"])
        self.assertIn("average_rating", response.data["reputation"])
        self.assertIn("reviews_count", response.data["reputation"])
        self.assertIn("completed_loans_count", response.data["reputation"])
        self.assertNotIn("phone_number", response.data)
        self.assertNotIn("address", response.data)
        self.assertNotIn("email", response.data)

        inactive_url = reverse(
            "authentication_api:profile-detail", args=[self.inactive_user.username]
        )
        self.assertEqual(
            self.client.get(inactive_url).status_code, status.HTTP_404_NOT_FOUND
        )

    def test_profile_me_anonymous_returns_403(self):
        self.assertEqual(self.client.get(self.me_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.put(self.me_url, {}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.patch(self.me_url, {}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_profile_me_authenticated_and_auto_creates_profile(self):
        new_user = User.objects.create_user(
            username="baru", email="baru@ui.ac.id", password=self.password
        )
        self.assertFalse(UserProfile.objects.filter(user=new_user).exists())
        self.client.force_authenticate(user=new_user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(UserProfile.objects.filter(user=new_user).exists())
        self.assertEqual(response.data["username"], "baru")
        self.assertEqual(response.data["email"], "baru@ui.ac.id")
        self.assertIn("phone_number", response.data)
        self.assertIn("address", response.data)
        self.assertIn("reputation", response.data)

    def test_profile_me_put_and_patch_valid_and_read_only_protection(self):
        self.client.force_authenticate(user=self.user)
        patch_res = self.client.patch(
            self.me_url,
            {
                "full_name": "<b>Azka Updated</b>",
                "address": "<i>Kutek</i>, Depok",
                "phone_number": "+62 812-3456-7890",
                "is_verified": True,
                "auth_provider": "sso_ui",
            },
            format="json",
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Azka Updated")
        self.assertEqual(self.profile.address, "Kutek, Depok")
        self.assertEqual(self.profile.phone_number, "+62 812-3456-7890")
        self.assertFalse(self.profile.is_verified)
        self.assertEqual(self.profile.auth_provider, UserProfile.AuthProvider.LOCAL)

        put_res = self.client.put(
            self.me_url,
            {
                "full_name": "Azka Full",
                "npm": "2506612410",
                "phone_number": "(021) 786-1234",
                "address": "Pondok Cina, Depok",
                "profile_picture_url": "https://example.com/new.png",
            },
            format="json",
        )
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Azka Full")
        self.assertEqual(
            self.profile.profile_picture_url, "https://example.com/new.png"
        )

    def test_profile_me_validation_errors(self):
        self.client.force_authenticate(user=self.user)
        invalid_cases = [
            ({"full_name": '<img src="x" onerror="alert(1)">'}, "full_name"),
            ({"address": '<img src="x" onerror="alert(1)">'}, "address"),
            ({"npm": "2506ABCDEF"}, "npm"),
            ({"phone_number": "BUKAN_NOMOR_HP!@#"}, "phone_number"),
            ({"profile_picture_url": "ftp://example.com/pic.jpg"}, "profile_picture_url"),
            ({"profile_picture_url": "javascript:alert(1)"}, "profile_picture_url"),
        ]
        for payload, expected_field in invalid_cases:
            response = self.client.patch(self.me_url, payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn(expected_field, response.data)

    def test_sso_ui_npm_protection(self):
        self.profile.auth_provider = UserProfile.AuthProvider.SSO_UI
        self.profile.npm = "2506999999"
        self.profile.is_verified = True
        self.profile.save()

        self.client.force_authenticate(user=self.user)
        # Mengubah field lain tanpa menyentuh NPM diizinkan
        ok_res = self.client.patch(
            self.me_url, {"full_name": "Azka Civitas UI"}, format="json"
        )
        self.assertEqual(ok_res.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.npm, "2506999999")

        # Mencoba mengubah NPM untuk akun SSO UI ditolak
        bad_res = self.client.patch(
            self.me_url, {"npm": "2506000000"}, format="json"
        )
        self.assertEqual(bad_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("npm", bad_res.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.npm, "2506999999")

    def test_login_help_request_anonymous_vs_authenticated(self):
        payload = {
            "email_or_username": "<b>azka</b>",
            "contact_email": "AZKA.HELP@example.com",
            "issue_type": LoginHelpRequest.IssueType.FORGOT_PASSWORD,
            "message": "<script>alert(1)</script>Lupa kata sandi akun lokal.",
        }
        response = self.client.post(self.help_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["detail"],
            "Permohonan bantuan Anda telah diterima. Jika akun terdaftar, admin akan menghubungi email kontakmu.",
        )
        req_obj = LoginHelpRequest.objects.get()
        self.assertEqual(req_obj.email_or_username, "azka")
        self.assertEqual(req_obj.contact_email, "azka.help@example.com")
        self.assertNotIn("<script>", req_obj.message)

        # Input kosong setelah strip_tags ditolak
        bad_res = self.client.post(
            self.help_url,
            {
                "email_or_username": '<img src="x" onerror="alert(1)">',
                "contact_email": "help@example.com",
                "issue_type": LoginHelpRequest.IssueType.OTHER,
                "message": "   ",
            },
            format="json",
        )
        self.assertEqual(bad_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email_or_username", bad_res.data)
        self.assertIn("message", bad_res.data)

        # User login ditolak dengan 403
        self.client.force_authenticate(user=self.user)
        auth_res = self.client.post(self.help_url, payload, format="json")
        self.assertEqual(auth_res.status_code, status.HTTP_403_FORBIDDEN)

        # Method GET ditolak dengan 405
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(self.help_url).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_session_write_without_csrf_is_rejected(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username="azka", password=self.password))
        response = client.patch(
            self.me_url, {"full_name": "Tanpa CSRF"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Azka Nur Jauhar")

    def test_session_write_with_csrf_succeeds(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username="azka", password=self.password))
        page = client.get(self.me_url, HTTP_ACCEPT="text/html")
        self.assertEqual(page.status_code, status.HTTP_200_OK)
        token = client.cookies["csrftoken"].value
        response = client.patch(
            self.me_url,
            {"full_name": "Dengan CSRF"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Dengan CSRF")
