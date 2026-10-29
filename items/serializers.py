from django.templatetags.static import static


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
