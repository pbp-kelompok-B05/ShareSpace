import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import Q

from items.models import Item
from items.validators import StrippedMinLengthValidator


class Report(models.Model):
    """Laporan pengguna terhadap barang atau pengguna lain.

    Target transaksi (LoanRequest) ditambahkan setelah modul loans di-merge ke dev.
    """

    class Reason(models.TextChoices):
        ITEM_MISMATCH = "item_mismatch", "Barang tidak sesuai deskripsi"
        ITEM_DAMAGED = "item_damaged", "Barang rusak atau tidak berfungsi"
        LATE_RETURN = "late_return", "Barang terlambat dikembalikan"
        UNRESPONSIVE = "unresponsive", "Pengguna tidak merespons"
        MISCONDUCT = "misconduct", "Perilaku tidak pantas saat COD"
        OTHER = "other", "Lainnya"

    class Status(models.TextChoices):
        PENDING = "pending", "Menunggu"
        REVIEWING = "reviewing", "Ditinjau"
        RESOLVED = "resolved", "Selesai"
        REJECTED = "rejected", "Ditolak"

    ACTIVE_STATUSES = (Status.PENDING, Status.REVIEWING)
    # Menunggu → Ditinjau → Selesai / Ditolak. Laporan spam boleh langsung ditolak.
    ALLOWED_TRANSITIONS = {
        Status.PENDING: {Status.REVIEWING, Status.REJECTED},
        Status.REVIEWING: {Status.RESOLVED, Status.REJECTED},
        Status.RESOLVED: set(),
        Status.REJECTED: set(),
    }

    # UUID agar URL laporan tidak bisa ditebak berurutan.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reports_made",
    )
    target_item = models.ForeignKey(
        "items.Item",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reports",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reports_received",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    description = models.TextField(
        max_length=1000,
        validators=[StrippedMinLengthValidator(20), MaxLengthValidator(1000)],
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    # Tanggapan admin yang bisa dibaca pelapor.
    admin_note = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="review_report_status_idx"),
            models.Index(fields=["-created_at"], name="review_report_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(target_item__isnull=False, target_user__isnull=True)
                    | Q(target_item__isnull=True, target_user__isnull=False)
                ),
                name="review_report_exactly_one_target",
                violation_error_message="Pilih tepat satu target laporan: barang atau pengguna.",
            ),
            # Satu pelapor hanya boleh punya satu laporan aktif per target.
            models.UniqueConstraint(
                fields=["reporter", "target_item"],
                condition=Q(status__in=["pending", "reviewing"]),
                name="review_report_one_active_per_item",
                violation_error_message="Kamu masih punya laporan aktif untuk barang ini.",
            ),
            models.UniqueConstraint(
                fields=["reporter", "target_user"],
                condition=Q(status__in=["pending", "reviewing"]),
                name="review_report_one_active_per_user",
                violation_error_message="Kamu masih punya laporan aktif untuk pengguna ini.",
            ),
        ]

    def __str__(self):
        return f"Laporan {self.get_reason_display()} ({self.get_status_display()})"

    def clean(self):
        errors = {}
        if self.target_user_id and self.target_user_id == self.reporter_id:
            errors["target_user"] = "Kamu tidak dapat melaporkan dirimu sendiri."
        if self.target_item_id and self.reporter_id:
            # Validasi FK Django memakai base manager, jadi barang soft delete dicek manual.
            target = (
                Item.all_objects
                .filter(pk=self.target_item_id)
                .values("owner_id", "is_deleted")
                .first()
            )
            if target and target["is_deleted"] and self._state.adding:
                # Hanya untuk laporan baru; laporan lama tetap bisa diedit walau barang dihapus.
                errors["target_item"] = "Barang ini sudah dihapus dan tidak dapat dilaporkan."
            elif target and target["owner_id"] == self.reporter_id:
                errors["target_item"] = "Kamu tidak dapat melaporkan barang milikmu sendiri."
        if errors:
            raise ValidationError(errors)

    @property
    def target(self):
        return self.target_item if self.target_item_id else self.target_user

    @property
    def target_type(self):
        return "item" if self.target_item_id else "user"

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    def is_editable_by(self, user):
        """Pelapor hanya boleh mengubah/membatalkan laporan yang belum ditinjau."""
        return user.pk == self.reporter_id and self.status == self.Status.PENDING

    def can_transition_to(self, status):
        return status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    @property
    def next_statuses(self):
        """Status tujuan yang valid, urut sesuai alur (untuk tombol aksi admin)."""
        return [status for status in self.Status if self.can_transition_to(status)]

    def transition_to(self, status, note=None):
        """Ubah status sesuai alur moderasi. note=None mempertahankan catatan admin lama."""
        if not self.can_transition_to(status):
            raise ValidationError(
                f"Status laporan tidak dapat diubah dari "
                f"{self.get_status_display()} ke {self.Status(status).label}."
            )
        self.status = status
        update_fields = ["status", "updated_at"]
        if note is not None:
            self.admin_note = note
            update_fields.append("admin_note")
        self.save(update_fields=update_fields)
