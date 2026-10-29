import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from items.models import Item
from items.validators import StrippedMinLengthValidator
from loans.models import LoanRequest


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


class ReviewQuerySet(models.QuerySet):
    def visible(self):
        """Ulasan yang tampil publik (tidak disembunyikan admin)."""
        return self.filter(is_hidden=False)


class Review(models.Model):
    """Ulasan satu pihak terhadap pihak lain setelah transaksi peminjaman selesai.

    Setiap transaksi bisa punya dua ulasan: peminjam menilai pemilik, dan sebaliknya.
    Buat lewat Review.for_loan() agar reviewee dan peran terisi otomatis.
    """

    class Role(models.TextChoices):
        BORROWER = "borrower", "Peminjam"
        LENDER = "lender", "Pemilik barang"

    MIN_RATING = 1
    MAX_RATING = 5

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(
        "loans.LoanRequest",
        on_delete=models.PROTECT,
        related_name="reviews",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviews_written",
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviews_received",
    )
    # Peran penulis ulasan dalam transaksi (peminjam menilai pemilik, atau sebaliknya).
    reviewer_role = models.CharField(max_length=10, choices=Role.choices)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_RATING), MaxValueValidator(MAX_RATING)],
    )
    comment = models.TextField(max_length=1000, blank=True, validators=[MaxLengthValidator(1000)])
    # Moderasi admin: ulasan tidak pantas disembunyikan, bukan dihapus.
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ReviewQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["reviewee", "is_hidden"], name="review_reviewee_idx"),
            models.Index(fields=["-created_at"], name="review_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5),
                name="review_rating_range",
                violation_error_message="Rating harus antara 1 dan 5.",
            ),
            models.UniqueConstraint(
                fields=["loan", "reviewer"],
                name="review_one_per_reviewer_per_loan",
                violation_error_message="Kamu sudah memberi ulasan untuk transaksi ini.",
            ),
            models.CheckConstraint(
                condition=~Q(reviewer=F("reviewee")),
                name="review_not_self",
                violation_error_message="Kamu tidak dapat mengulas dirimu sendiri.",
            ),
        ]

    def __str__(self):
        return f"{self.rating}★ untuk {self.reviewee} ({self.get_reviewer_role_display()})"

    @staticmethod
    def _counterpart(loan, user):
        """(reviewee, peran reviewer) untuk user dalam loan, atau None jika bukan pihak transaksi."""
        # loan.item lewat base manager, jadi barang yang sudah di-soft delete tetap terbaca.
        if user.pk == loan.borrower_id:
            return loan.item.owner, Review.Role.BORROWER
        if user.pk == loan.item.owner_id:
            return loan.borrower, Review.Role.LENDER
        return None

    @classmethod
    def for_loan(cls, loan, reviewer):
        """Ulasan baru (belum disimpan) dengan reviewee dan peran terisi otomatis."""
        counterpart = cls._counterpart(loan, reviewer)
        if counterpart is None:
            raise ValidationError("Hanya pihak dalam transaksi ini yang dapat memberi ulasan.")
        reviewee, role = counterpart
        return cls(loan=loan, reviewer=reviewer, reviewee=reviewee, reviewer_role=role)

    @classmethod
    def can_be_written(cls, loan, user):
        """True jika user boleh menulis ulasan baru untuk loan (untuk tombol "Beri ulasan")."""
        if not user.is_authenticated or cls._counterpart(loan, user) is None:
            return False
        if loan.status != LoanRequest.Status.COMPLETED:
            return False
        return not cls.objects.filter(loan=loan, reviewer=user).exists()

    def clean(self):
        # Pesan dibuat tanpa kunci field: ModelForm ulasan hanya memuat rating dan komentar.
        if not self.loan_id or not self.reviewer_id:
            return
        if self.loan.status != LoanRequest.Status.COMPLETED:
            raise ValidationError("Ulasan hanya dapat diberikan setelah transaksi selesai.")
        counterpart = self._counterpart(self.loan, self.reviewer)
        if counterpart is None:
            raise ValidationError("Hanya pihak dalam transaksi ini yang dapat memberi ulasan.")
        reviewee, role = counterpart
        if self.reviewee_id != reviewee.pk or self.reviewer_role != role:
            raise ValidationError("Ulasan harus ditujukan ke pihak lain dalam transaksi ini.")

    def is_editable_by(self, user):
        """Penulis boleh mengubah/menghapus ulasannya, kecuali sudah disembunyikan admin."""
        return user.pk == self.reviewer_id and not self.is_hidden
