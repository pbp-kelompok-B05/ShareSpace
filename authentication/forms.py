from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import EmailInput, ModelForm, Select, TextInput, Textarea, URLInput
from django.utils.html import strip_tags

from authentication.models import LoginHelpRequest, UserProfile


class UserProfileForm(ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "full_name",
            "npm",
            "phone_number",
            "address",
            "profile_picture_url",
        ]

        labels = {
            "full_name": "Nama Lengkap",
            "npm": "Nomor Pokok Mahasiswa (NPM)",
            "phone_number": "Nomor Telepon",
            "address": "Domisili / Alamat Kost",
            "profile_picture_url": "URL Foto Profil (Opsional)",
        }

        help_texts = {
            "full_name": "Nama lengkap yang akan tampil di ulasan dan profil.",
            "npm": "Nomor Pokok Mahasiswa (opsional, diverifikasi otomatis jika login via SSO UI).",
            "phone_number": "Nomor WhatsApp aktif untuk koordinasi serah terima barang COD.",
            "address": "Alamat domisili atau kost di sekitar kampus.",
            "profile_picture_url": "Tautan gambar foto profil yang valid (diawali http:// atau https://).",
        }

        widgets = {
            "full_name": TextInput(
                attrs={
                    "placeholder": "Masukkan nama lengkap Anda",
                    "maxlength": 255,
                }
            ),
            "npm": TextInput(
                attrs={
                    "placeholder": "Contoh: 2506123456",
                    "maxlength": 20,
                }
            ),
            "phone_number": TextInput(
                attrs={
                    "placeholder": "Contoh: 081234567890",
                    "maxlength": 20,
                }
            ),
            "address": Textarea(
                attrs={
                    "placeholder": "Contoh: Kukusan Teknik, Beji, Depok",
                    "rows": 3,
                    "maxlength": 500,
                }
            ),
            "profile_picture_url": URLInput(
                attrs={
                    "placeholder": "https://example.com/foto-profil.jpg",
                    "maxlength": 500,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.auth_provider == UserProfile.AuthProvider.SSO_UI:
            self.fields["npm"].disabled = True
            self.fields["npm"].help_text = "NPM diverifikasi resmi via SSO UI dan tidak dapat diubah."

    def clean_full_name(self):
        full_name = self.cleaned_data.get("full_name", "")
        return strip_tags(full_name).strip()

    def clean_npm(self):
        if self.instance and self.instance.pk and self.instance.auth_provider == UserProfile.AuthProvider.SSO_UI:
            return self.instance.npm
        npm = self.cleaned_data.get("npm", "")
        if npm:
            npm = strip_tags(npm).strip()
            if not npm.isdigit():
                raise ValidationError("NPM hanya boleh memuat angka.")
        return npm

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number", "")
        cleaned_phone = strip_tags(phone_number).strip()
        if cleaned_phone and not all(c.isdigit() or c in "+ -()" for c in cleaned_phone):
            raise ValidationError("Nomor telepon hanya boleh memuat angka dan karakter pemisah yang valid.")
        return cleaned_phone

    def clean_address(self):
        address = self.cleaned_data.get("address", "")
        return strip_tags(address).strip()

    def clean_profile_picture_url(self):
        url = self.cleaned_data.get("profile_picture_url", "")
        if url:
            url = strip_tags(url).strip()
            if not (url.startswith("http://") or url.startswith("https://")):
                raise ValidationError("URL foto profil harus diawali dengan http:// atau https://.")
        return url

class LoginHelpRequestForm(ModelForm):
    class Meta:
        model = LoginHelpRequest
        fields = [
            "email_or_username",
            "contact_email",
            "issue_type",
            "message",
        ]

        labels = {
            "email_or_username": "Username atau Email Akun",
            "contact_email": "Email Kontak Aktif",
            "issue_type": "Jenis Kendala",
            "message": "Detail Kendala",
        }

        help_texts = {
            "email_or_username": "Masukkan username atau email akun yang bermasalah.",
            "contact_email": "Email aktif yang dapat kami hubungi untuk proses bantuan.",
            "issue_type": "Pilih jenis kendala yang paling sesuai dengan situasi Anda.",
            "message": "Jelaskan kronologi atau kendala login yang dialami secara jelas.",
        }

        widgets = {
            "email_or_username": TextInput(
                attrs={
                    "placeholder": "Contoh: frieren atau frieren@ui.ac.id",
                    "maxlength": 255,
                }
            ),
            "contact_email": EmailInput(
                attrs={
                    "placeholder": "nama@email.com",
                    "maxlength": 254,
                }
            ),
            "issue_type": Select(),
            "message": Textarea(
                attrs={
                    "placeholder": "Ceritakan kendala yang Anda alami saat mencoba masuk...",
                    "rows": 4,
                    "maxlength": 1000,
                }
            ),
        }

    def clean_email_or_username(self):
        val = strip_tags(self.cleaned_data.get("email_or_username", "")).strip()
        if val and not User.objects.filter(Q(username__iexact=val) | Q(email__iexact=val)).exists():
            raise ValidationError("Akun dengan username atau email tersebut tidak ditemukan di ShareSpace.")
        return val

    def clean_contact_email(self):
        contact_email = self.cleaned_data.get("contact_email", "")
        return strip_tags(contact_email).strip().lower()

    def clean_message(self):
        message = self.cleaned_data.get("message", "")
        return strip_tags(message).strip()

