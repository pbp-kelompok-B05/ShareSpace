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

    def has_filters(self):
        """Ada filter valid yang mempersempit hasil; sort tidak dihitung (untuk empty state)."""
        self.is_valid()
        return any(self.cleaned_data.get(name) for name in ("q", "category", "condition", "available"))


class MyItemsFilterForm(CatalogFilterForm):
    """Filter "Barang saya": filter katalog + tab status (aktif/terhapus). Status bukan filter."""

    STATUS_CHOICES = [("active", "Aktif"), ("deleted", "Terhapus")]

    status = forms.ChoiceField(label="Tampilkan", required=False, choices=STATUS_CHOICES)

    @property
    def show_deleted(self):
        self.is_valid()
        return self.cleaned_data.get("status") == "deleted"


class BulkItemActionForm(forms.Form):
    """Aksi massal untuk barang milik sendiri.

    Pilihan dibatasi ke barang milik `user` (termasuk yang terhapus, untuk dipulihkan), jadi satu pk
    milik orang lain membuat seluruh form tidak valid dan tidak ada barang yang berubah.
    """

    MAX_ITEMS = 100
    SKIPPED_REASONS = {
        "delete": "karena sedang dipinjam",
        "restore": "karena belum dihapus",
    }

    action = forms.ChoiceField(
        choices=[("delete", "Hapus"), ("restore", "Pulihkan")],
        error_messages={
            "required": "Aksi wajib dipilih.",
            "invalid_choice": "Aksi tidak dikenal.",
        },
    )
    items = forms.ModelMultipleChoiceField(
        queryset=Item.all_objects.none(),
        error_messages={
            "required": "Pilih minimal satu barang.",
            "invalid_choice": "Ada barang yang tidak ditemukan atau bukan milikmu.",
            "invalid_pk_value": "Ada barang yang tidak ditemukan atau bukan milikmu.",
        },
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["items"].queryset = Item.all_objects.filter(owner=user)

    def clean_items(self):
        items = self.cleaned_data["items"]
        if len(items) > self.MAX_ITEMS:
            raise forms.ValidationError(f"Maksimal {self.MAX_ITEMS} barang per aksi.")
        return items

    def save(self):
        """Jalankan aksi; kembalikan (jumlah berubah, jumlah dilewati)."""
        items = self.cleaned_data["items"]
        if self.cleaned_data["action"] == "delete":
            changed = items.soft_delete()
        else:
            changed = items.restore()
        return changed, len(items) - changed

    def result_message(self, changed, skipped):
        """Pesan toast, mis. "2 barang dihapus. 1 barang dilewati karena sedang dipinjam."."""
        action = self.cleaned_data["action"]
        verb = "dihapus" if action == "delete" else "dipulihkan"
        message = f"{changed} barang {verb}." if changed else f"Tidak ada barang yang {verb}."
        if skipped:
            message += f" {skipped} barang dilewati {self.SKIPPED_REASONS[action]}."
        return message


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
