from django.utils.html import strip_tags
from rest_framework import serializers

from authentication.models import LoginHelpRequest, UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    auth_provider_display = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "npm",
            "phone_number",
            "address",
            "profile_picture_url",
            "auth_provider",
            "auth_provider_display",
            "is_verified",
        ]
        read_only_fields = ["id", "auth_provider", "is_verified"]

    def get_auth_provider_display(self, obj):
        return obj.get_auth_provider_display()

    def validate_full_name(self, value):
        raw = (value or "").strip()
        cleaned = strip_tags(raw).strip()
        if raw and not cleaned:
            raise serializers.ValidationError("Nama lengkap tidak boleh hanya berisi tag HTML.")
        return cleaned

    def validate_npm(self, value):
        if (
            self.instance
            and self.instance.pk
            and self.instance.auth_provider == UserProfile.AuthProvider.SSO_UI
        ):
            if "npm" in self.initial_data:
                submitted = strip_tags(str(self.initial_data.get("npm") or "")).strip()
                if submitted != self.instance.npm:
                    raise serializers.ValidationError(
                        "NPM diverifikasi resmi via SSO UI dan tidak dapat diubah."
                    )
            return self.instance.npm

        raw = (value or "").strip()
        cleaned = strip_tags(raw).strip()
        if raw and not cleaned:
            raise serializers.ValidationError("NPM tidak boleh hanya berisi tag HTML.")
        if cleaned and not cleaned.isdigit():
            raise serializers.ValidationError("NPM hanya boleh memuat angka.")
        return cleaned

    def validate_phone_number(self, value):
        raw = (value or "").strip()
        cleaned_phone = strip_tags(raw).strip()
        if raw and not cleaned_phone:
            raise serializers.ValidationError("Nomor telepon tidak boleh hanya berisi tag HTML.")
        if cleaned_phone and not all(c.isdigit() or c in "+ -()" for c in cleaned_phone):
            raise serializers.ValidationError(
                "Nomor telepon hanya boleh memuat angka dan karakter pemisah yang valid."
            )
        return cleaned_phone

    def validate_address(self, value):
        raw = (value or "").strip()
        cleaned = strip_tags(raw).strip()
        if raw and not cleaned:
            raise serializers.ValidationError("Alamat tidak boleh hanya berisi tag HTML.")
        return cleaned

    def validate_profile_picture_url(self, value):
        if not value:
            return value
        cleaned_url = strip_tags(value).strip()
        if cleaned_url and not (
            cleaned_url.startswith("http://") or cleaned_url.startswith("https://")
        ):
            raise serializers.ValidationError(
                "URL foto profil harus diawali dengan http:// atau https://."
            )
        return cleaned_url


class PublicUserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    auth_provider_display = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "full_name",
            "profile_picture_url",
            "auth_provider",
            "auth_provider_display",
            "is_verified",
        ]
        read_only_fields = fields

    def get_auth_provider_display(self, obj):
        return obj.get_auth_provider_display()


class LoginHelpRequestSerializer(serializers.ModelSerializer):
    issue_type_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = LoginHelpRequest
        fields = [
            "id",
            "email_or_username",
            "contact_email",
            "issue_type",
            "issue_type_display",
            "message",
            "status",
            "status_display",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def get_issue_type_display(self, obj):
        return obj.get_issue_type_display()

    def get_status_display(self, obj):
        return obj.get_status_display()

    def validate_email_or_username(self, value):
        cleaned = strip_tags(value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Username atau email akun tidak boleh kosong.")
        return cleaned

    def validate_contact_email(self, value):
        cleaned = strip_tags(value or "").strip().lower()
        if not cleaned:
            raise serializers.ValidationError("Email kontak aktif tidak boleh kosong.")
        return cleaned

    def validate_message(self, value):
        cleaned = strip_tags(value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Detail kendala tidak boleh kosong.")
        return cleaned
