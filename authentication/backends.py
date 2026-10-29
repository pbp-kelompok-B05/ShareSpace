import re
import requests

from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from authentication.models import UserProfile


class BaseExternalAuthBackend(BaseBackend):
    """
    Base Authentication Backend untuk penyedia autentikasi eksternal.
    Sesuai panduan resmi Django Docs (Custom Authentication Backends).
    Menerapkan inheritance, polymorphism, dan prinsip OOP SOLID.
    """

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist as e:
            return None

    def get_or_create_user(
        self,
        username,
        email,
        full_name,
        auth_provider,
        is_verified=True,
        npm="",
        profile_picture_url="",
    ):
        """
        Helper method bersama untuk mendapatkan atau membuat akun User dan UserProfile.
        """
        user = None
        if email:
            user = User.objects.filter(email__iexact=email).first()

        if not user:
            base_username = username
            counter = 1
            while User.objects.filter(username__iexact=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=email,
            )
            user.set_unusable_password()
            user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if full_name and not profile.full_name:
            profile.full_name = full_name
        if npm and not profile.npm:
            profile.npm = npm
        if profile_picture_url and not profile.profile_picture_url:
            profile.profile_picture_url = profile_picture_url

        if profile.auth_provider == UserProfile.AuthProvider.LOCAL:
            profile.auth_provider = auth_provider
        if is_verified:
            profile.is_verified = True
        profile.save()

        return user


class GoogleAuthBackend(BaseExternalAuthBackend):
    """
    Authentication Backend untuk Google Identity Services (GSI).
    Memverifikasi ID Token JWT melalui endpoint Google tokeninfo.
    """

    TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

    def verify_token(self, id_token):
        """Memverifikasi ID Token Google ke Google OAuth2 tokeninfo API."""
        try:
            response = requests.get(
                self.TOKENINFO_URL,
                params={"id_token": id_token},
                timeout=10,
            )
            if response.status_code == 200:
                payload = response.json()
                expected_client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
                if expected_client_id and payload.get("aud") and payload.get("aud") != expected_client_id:
                    return None
                return payload
            return None
        except Exception as e:
            return None

    def authenticate(self, request, google_credential=None, **kwargs):
        """Mengautentikasi pengguna Google dengan memverifikasi ID token."""
        if not google_credential:
            return None

        payload = self.verify_token(google_credential)
        if not payload:
            return None

        email = payload.get("email", "")
        if not email or payload.get("email_verified") not in (True, "true"):
            return None

        full_name = payload.get("name", "")
        picture = payload.get("picture", "")
        username = email.split("@")[0].lower()

        return self.get_or_create_user(
            username=username,
            email=email,
            full_name=full_name,
            auth_provider=UserProfile.AuthProvider.GOOGLE,
            is_verified=True,
            profile_picture_url=picture,
        )


class SSOUIAuthBackend(BaseExternalAuthBackend):
    """
    Authentication Backend untuk SSO UI (Central Authentication Service / CAS 2.0).
    Memvalidasi service ticket ke server CAS Universitas Indonesia.
    """

    CAS_LOGIN_URL = "https://sso.ui.ac.id/cas2/login"
    CAS_VALIDATE_URL = "https://sso.ui.ac.id/cas2/serviceValidate"

    @classmethod
    def get_login_url(cls, service_url):
        """Membuat URL redirect ke halaman login SSO UI."""
        return f"{cls.CAS_LOGIN_URL}?service={requests.utils.quote(service_url)}"

    def parse_cas_xml(self, xml_text):
        """Mengekstrak data pengguna dari payload XML CAS serviceResponse."""
        try:
            if "<cas:authenticationSuccess>" not in xml_text:
                return None

            def get_tag(tag):
                match = re.search(rf"<cas:{tag}>(.*?)</cas:{tag}>", xml_text)
                return match.group(1).strip() if match else ""

            username = get_tag("user")
            nama = get_tag("nama")
            npm = get_tag("npm")

            if not username:
                return None

            return {
                "username": username,
                "nama": nama,
                "npm": npm,
            }
        except Exception as e:
            return None

    def validate_ticket(self, ticket, service_url):
        """Memvalidasi tiket CAS ke endpoint serviceValidate SSO UI."""
        try:
            response = requests.get(
                self.CAS_VALIDATE_URL,
                params={"service": service_url, "ticket": ticket},
                timeout=10,
            )
            if response.status_code != 200:
                return None
            return self.parse_cas_xml(response.text)
        except Exception as e:
            return None

    def authenticate(self, request, sso_ticket=None, service_url=None, **kwargs):
        """Mengautentikasi pengguna SSO UI berdasarkan ticket CAS."""
        if not sso_ticket or not service_url:
            return None

        data = self.validate_ticket(sso_ticket, service_url)
        if not data or not data.get("username"):
            return None

        username = data["username"].lower()
        full_name = data.get("nama") or username
        npm = data.get("npm", "")
        email = f"{username}@ui.ac.id"

        return self.get_or_create_user(
            username=username,
            email=email,
            full_name=full_name,
            auth_provider=UserProfile.AuthProvider.SSO_UI,
            is_verified=True,
            npm=npm,
        )
