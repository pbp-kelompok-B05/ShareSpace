from django.core.exceptions import ValidationError
from django.forms import ModelForm, TextInput, Textarea, URLInput
from django.utils.html import strip_tags

from authentication.models import UserProfile


class UserProfileForm(ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "full_name",
            "phone_number",
            "address",
            "profile_picture_url",
        ]

        labels = {
            "full_name": "Nama Lengkap",
            "phone_number": "Nomor Telepon",
            "address": "Domisili / Alamat Kost",
            "profile_picture_url": "URL Foto Profil (Opsional)",
        }

        widgets = {
            "full_name": TextInput(
                attrs={
                    "placeholder": "Masukkan nama lengkap Anda",
                    "maxlength": 255,
                    "class": "auth-input",
                }
            ),
            "phone_number": TextInput(
                attrs={
                    "placeholder": "Contoh: 081234567890",
                    "maxlength": 20,
                    "class": "auth-input",
                }
            ),
            "address": Textarea(
                attrs={
                    "placeholder": "Contoh: Kukusan Teknik, Beji, Depok",
                    "rows": 3,
                    "maxlength": 500,
                    "class": "auth-input auth-textarea",
                }
            ),
            "profile_picture_url": URLInput(
                attrs={
                    "placeholder": "https://example.com/foto-profil.jpg",
                    "maxlength": 500,
                    "class": "auth-input",
                }
            ),
        }

    def clean_full_name(self):
        full_name = self.cleaned_data.get("full_name", "")
        return strip_tags(full_name).strip()

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
