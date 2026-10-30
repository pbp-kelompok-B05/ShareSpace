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
        db_default=AuthProvider.LOCAL,
        help_text="Penyedia autentikasi akun (Lokal, Google, atau SSO UI).",
    )
    is_verified = models.BooleanField(
        default=False,
        db_default=False,
        help_text="Status verifikasi pengguna (misal civitas UI atau akun terverifikasi).",
    )
    npm = models.CharField(
        max_length=20,
        blank=True,
        default="",
        db_default="",
        help_text="Nomor Pokok Mahasiswa (khusus pengguna SSO UI).",
    )

    @property
    def is_external_auth(self):
        """Mengetahui apakah pengguna terdaftar melalui penyedia autentikasi eksternal."""
        return self.auth_provider in (self.AuthProvider.GOOGLE, self.AuthProvider.SSO_UI)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class LoginHelpRequest(models.Model):
    class IssueType(models.TextChoices):
        FORGOT_PASSWORD = "forgot_password", "Lupa Password Akun Lokal"
        ACCOUNT_LOCKED = "account_locked", "Akun Terkunci / Dinonaktifkan"
        OTHER = "other", "Kendala Login Lainnya"

    class Status(models.TextChoices):
        PENDING = "pending", "Menunggu Bantuan"
        RESOLVED = "resolved", "Selesai Ditangani"

    email_or_username = models.CharField(
        max_length=255,
        help_text="Username atau email akun yang mengalami kendala.",
    )
    contact_email = models.EmailField(
        help_text="Email aktif yang dapat dihubungi oleh admin.",
    )
    issue_type = models.CharField(
        max_length=30,
        choices=IssueType.choices,
        default=IssueType.FORGOT_PASSWORD,
        help_text="Jenis kendala yang dialami pengguna.",
    )
    message = models.TextField(
        max_length=1000,
        help_text="Penjelasan detail kendala dari pengguna.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Status tindak lanjut permohonan bantuan.",
    )
    admin_notes = models.TextField(
        blank=True,
        max_length=1000,
        help_text="Catatan internal admin saat menindaklanjuti kendala.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Permohonan Bantuan Login"
        verbose_name_plural = "Permohonan Bantuan Login"

    def __str__(self):
        return f"{self.email_or_username} ({self.get_issue_type_display()}) - {self.get_status_display()}"
