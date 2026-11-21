from django.core.exceptions import ValidationError as DjangoValidationError
from django.templatetags.static import static
from django.utils.html import strip_tags
from rest_framework import serializers

from items.models import Item


class ItemSerializer(serializers.ModelSerializer):
    """Kontrak JSON API barang (/api/v1/items/): representasi sekaligus validasi input.

    Field sistem (owner, is_available, is_verified, created_at) dan field hasil perhitungan
    read-only, jadi klien tidak bisa mengisinya. Pemilik diisi view dari request.user.
    """

    category_display = serializers.CharField(source="get_category_display", read_only=True)
    condition_display = serializers.CharField(source="get_condition_display", read_only=True)
    image = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = [
            "id", "name", "description", "category", "category_display", "condition",
            "condition_display", "image_url", "image", "is_available", "is_verified",
            "owner", "created_at",
        ]
        read_only_fields = ["id", "is_available", "is_verified", "created_at"]

    @staticmethod
    def _run_model_validators(field_name, value):
        try:
            for validator in Item._meta.get_field(field_name).validators:
                validator(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages)

    def _clean_text(self, field_name, value):
        """Buang tag HTML, lalu jalankan ulang validator model pada hasilnya.

        Validator field berjalan sebelum validate_<field>, jadi "<b></b>" lolos batas
        minimal panjang; tanpa pengecekan ulang ia menjadi string kosong setelah dibersihkan.
        """
        cleaned = strip_tags(value).strip()
        self._run_model_validators(field_name, cleaned)
        return cleaned

    def validate_name(self, value):
        return self._clean_text("name", value)

    def validate_description(self, value):
        return self._clean_text("description", value)

    def validate_image_url(self, value):
        # URLField DRF memakai URLValidator bawaan (ftp:// lolos); terapkan validator model (http/https).
        if value:
            self._run_model_validators("image_url", value)
        return value

    def get_image(self, obj):
        # URL absolut agar langsung bisa dipakai klien di luar browser (Flutter).
        request = self.context["request"]
        return obj.image_url or request.build_absolute_uri(static(obj.placeholder_path))

    def get_owner(self, obj):
        return {"id": obj.owner_id, "username": obj.owner.get_username()}


def serialize_item(item, request):
    """Data publik satu barang untuk respons JSON. Owner wajib sudah di-select_related."""
    return {
        "id": item.pk,
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "category_display": item.get_category_display(),
        "condition": item.condition,
        "condition_display": item.get_condition_display(),
        "image_url": item.image_url,
        # URL absolut agar langsung bisa dipakai klien di luar browser (Flutter).
        "image": item.image_url or request.build_absolute_uri(static(item.placeholder_path)),
        "is_available": item.is_available,
        "is_verified": item.is_verified,
        "owner": {"id": item.owner_id, "username": item.owner.get_username()},
        "created_at": item.created_at.isoformat(),
    }
