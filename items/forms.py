from django import forms
from django.db import models
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


def _item_formfield(db_field, **kwargs):
    # Tanpa skema ("contoh.com/foto.jpg") dianggap https; sekaligus menghindari warning Django 6.0.
    if isinstance(db_field, models.URLField):
        kwargs["assume_scheme"] = "https"
    return db_field.formfield(**kwargs)


class ItemForm(forms.ModelForm):
    """Form tambah/edit barang oleh pemilik.

    Field sistem (owner, is_available, is_verified, is_deleted) sengaja tidak ada,
    jadi tidak bisa diisi lewat POST. Batas panjang divalidasi ulang oleh validator model.
    """

    class Meta:
        model = Item
        fields = ["name", "description", "category", "condition", "image_url"]
        formfield_callback = _item_formfield
        labels = {
            "name": "Nama barang",
            "description": "Deskripsi",
            "category": "Kategori",
            "condition": "Kondisi",
            "image_url": "URL foto",
        }
        help_texts = {
            "name": "3–100 karakter.",
            "description": "20–1000 karakter. Ceritakan kelengkapan, kondisi, dan catatan pemakaian.",
            "image_url": "Opsional. Tautan http/https ke foto barang; jika kosong dipakai gambar bawaan kategori.",
        }
        widgets = {
            "name": forms.TextInput(attrs={
                "minlength": "3",
                "placeholder": "Contoh: Tenda Dome 4 Orang",
            }),
            "description": forms.Textarea(attrs={
                "rows": 5,
                "minlength": "20",
                "placeholder": "Contoh: Tenda kapasitas 4 orang, lengkap dengan frame, pasak, dan flysheet.",
            }),
            "image_url": forms.URLInput(attrs={"placeholder": "https://contoh.com/foto-barang.jpg"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].choices = [("", "Pilih kategori"), *Item.Category.choices]
        self.fields["condition"].choices = [("", "Pilih kondisi"), *Item.Condition.choices]

    def full_clean(self):
        super().full_clean()
        # HTMX memfokus elemen ber-autofocus setelah swap: arahkan ke field error pertama.
        for name, field in self.fields.items():
            if name in self.errors:
                field.widget.attrs["autofocus"] = True
                break
