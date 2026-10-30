from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class UserProfile(models.Model):
    class AuthProvider(models.TextChoices):
        LOCAL = "local", "Lokal"
        GOOGLE = "google", "Google"
        SSO_UI = "sso_ui", "SSO UI"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
    )
    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    profile_picture_url = models.URLField(max_length=500, blank=True, null=True)
    auth_provider = models.CharField(
        max_length=20,
        choices=AuthProvider.choices,
        default=AuthProvider.LOCAL,
        blank=True,
        null=True,
        help_text="Penyedia autentikasi akun (Lokal, Google, atau SSO UI).",
    )
    is_verified = models.BooleanField(
        default=False,
        blank=True,
        null=True,
        help_text="Status verifikasi pengguna (misal civitas UI atau akun terverifikasi).",
    )
    npm = models.CharField(
        max_length=20,
        blank=True,
        default="",
        null=True,
        help_text="Nomor Pokok Mahasiswa (khusus pengguna SSO UI).",
    )

    @property
    def is_external_auth(self):
        """Mengetahui apakah pengguna terdaftar melalui penyedia autentikasi eksternal."""
        return self.auth_provider in (self.AuthProvider.GOOGLE, self.AuthProvider.SSO_UI)

    def __str__(self):
        return f"{self.user.username}'s Profile"
