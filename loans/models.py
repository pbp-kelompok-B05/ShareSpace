import uuid
from django.conf import settings
from django.db import models
from django.db.models import F, Q

# Create your models here.

class LoanRequest(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Menunggu konfirmasi"
        APPROVED = "approved", "Disetujui"
        BORROWED = "borrowed", "Sedang dipinjam"
        COMPLETED = "completed", "Selesai"
        REJECTED = "rejected", "Ditolak"
        CANCELLED = "cancelled", "Dibatalkan"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    borrower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="loan_requests",
    )
    item = models.ForeignKey(
        "items.Item",
        on_delete=models.PROTECT,
        related_name="loan_requests",
    )
    start_date = models.DateField()
    due_date = models.DateField()
    notes = models.TextField(blank=True)
    return_requested_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(due_date__gte=F("start_date")),
                name="loans_valid_date_range",
            ),
            models.UniqueConstraint(
                fields=["item"],
                condition=Q(status__in=["approved", "borrowed"]),
                name="loans_one_active_per_item",
            )
        ]

    def __str__(self):
        return f"Loan {self.item.name} - {self.get_status_display()}"
