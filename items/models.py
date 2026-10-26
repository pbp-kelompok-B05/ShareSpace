from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, URLValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from items.validators import StrippedMinLengthValidator


class ItemQuerySet(models.QuerySet):

    def visible(self):
        """Barang yang boleh tampil di katalog: pemiliknya masih aktif."""
        return self.filter(owner__is_active=True)


class ActiveItemManager(models.Manager.from_queryset(ItemQuerySet)):
    """Manager default: menyembunyikan barang yang sudah di-soft delete."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Item(models.Model):

    class Category(models.TextChoices):
        ELECTRONICS = "electronics", "Elektronik"
        HOUSEHOLD = "household", "Perkakas & Rumah Tangga"
        SPORTS = "sports", "Olahraga"
        BOOKS = "books", "Buku & Alat Tulis"
        HOBBY = "hobby", "Hobi & Musik"
        OUTDOOR = "outdoor", "Outdoor & Camping"
        OTHER = "other", "Lainnya"

    class Condition(models.TextChoices):
        LIKE_NEW = "like_new", "Seperti Baru"
        GOOD = "good", "Baik"
        FAIR = "fair", "Layak Pakai"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="items",
    )
    name = models.CharField(
        max_length=100,
        validators=[StrippedMinLengthValidator(3)],
    )
    description = models.TextField(
        max_length=1000,
        validators=[StrippedMinLengthValidator(20), MaxLengthValidator(1000)],
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    condition = models.CharField(max_length=20, choices=Condition.choices)
    image_url = models.URLField(
        max_length=500,
        blank=True,
        validators=[URLValidator(schemes=["http", "https"])],
    )
    # Hanya diubah modul transaksi (loans), bukan oleh pemilik.
    is_available = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Manager pertama menjadi manager default.
    objects = ActiveItemManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category"], name="items_category_idx"),
            models.Index(fields=["condition"], name="items_condition_idx"),
            models.Index(fields=["is_available"], name="items_available_idx"),
            models.Index(fields=["-created_at"], name="items_created_idx"),
        ]
        constraints = [
            # is_deleted dan deleted_at harus selalu konsisten.
            models.CheckConstraint(
                condition=(
                    Q(is_deleted=True, deleted_at__isnull=False)
                    | Q(is_deleted=False, deleted_at__isnull=True)
                ),
                name="items_deleted_at_consistent",
            ),
        ]

    def __str__(self):
        return self.name

    def soft_delete(self, force=False):
        """Sembunyikan barang. force=True hanya untuk jalur moderasi admin."""
        if self.is_deleted:
            return
        if not self.is_available and not force:
            raise ValidationError("Barang yang sedang dipinjam tidak dapat dihapus.")
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
