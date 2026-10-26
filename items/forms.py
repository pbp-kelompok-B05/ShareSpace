from django import forms
from django.db.models import Q

from items.models import Item


class CatalogFilterForm(forms.Form):
    """Filter katalog dari query string. Nilai yang tidak valid diabaikan, bukan error."""

    SORT_ORDERING = {
        "newest": ["-created_at", "-pk"],
        "oldest": ["created_at", "pk"],
        "name": ["name", "pk"],
        "name_desc": ["-name", "-pk"],
    }
    SORT_CHOICES = [
        ("newest", "Terbaru"),
        ("oldest", "Terlama"),
        ("name", "Nama A–Z"),
        ("name_desc", "Nama Z–A"),
    ]

    q = forms.CharField(
        label="Cari barang",
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            "type": "search",
            "placeholder": "Cari tenda, bor listrik, kamera, buku kalkulus…",
            "autocomplete": "off",
        }),
    )
    category = forms.ChoiceField(
        label="Kategori",
        required=False,
        choices=[("", "Semua")] + Item.Category.choices,
    )
    condition = forms.ChoiceField(
        label="Kondisi",
        required=False,
        choices=[("", "Semua Kondisi")] + Item.Condition.choices,
    )
    available = forms.BooleanField(label="Tersedia saja", required=False)
    sort = forms.ChoiceField(label="Urutkan", required=False, choices=SORT_CHOICES)

    def apply(self, queryset):
        self.is_valid()
        # Saat ada field tidak valid, cleaned_data hanya berisi field yang valid.
        data = self.cleaned_data
        if q := data.get("q"):
            queryset = queryset.filter(Q(name__icontains=q) | Q(description__icontains=q))
        if category := data.get("category"):
            queryset = queryset.filter(category=category)
        if condition := data.get("condition"):
            queryset = queryset.filter(condition=condition)
        if data.get("available"):
            queryset = queryset.filter(is_available=True)
        ordering = self.SORT_ORDERING.get(data.get("sort"), self.SORT_ORDERING["newest"])
        return queryset.order_by(*ordering)
