from django.db import models

# Create your models here.
from django.core.validators import MinValueValidator, MaxValueValidator

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class CODLocation(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(max_length=150)
    address = models.TextField()

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
    )

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cod_locations",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        super().clean()

        if self.latitude is not None:
            if not -90 <= self.latitude <= 90:
                raise ValidationError({
                    "latitude": "Latitude harus antara -90 dan 90."
                })

        if self.longitude is not None:
            if not -180 <= self.longitude <= 180:
                raise ValidationError({
                    "longitude": "Longitude harus antara -180 dan 180."
                })

    def __str__(self):
        return self.name


class PickupSchedule(models.Model):

    class ScheduleType(models.TextChoices):
        PICKUP = "pickup", "Pengambilan"
        RETURN = "return", "Pengembalian"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    loan_request = models.ForeignKey(
        "loans.LoanRequest",
        on_delete=models.CASCADE,
        related_name="cod_schedules",
    )

    cod_location = models.ForeignKey(
        CODLocation,
        on_delete=models.PROTECT,
        related_name="pickup_schedules",
    )

    schedule_type = models.CharField(
        max_length=10,
        choices=ScheduleType.choices,
    )

    scheduled_time = models.DateTimeField()

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_cod_schedules",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan_request", "schedule_type"],
                name="unique_cod_schedule_per_type",
            ),
        ]

    def clean(self):
        super().clean()

        if self.scheduled_time is not None:
            if self.scheduled_time < timezone.now():
                raise ValidationError({
                    "scheduled_time": "Jadwal tidak boleh di masa lalu."
                })

        if self.loan_request_id and self.created_by_id:
            loan = self.loan_request

            if self.created_by_id not in (
                loan.borrower_id,
                loan.item.owner_id,
            ):
                raise ValidationError(
                    "Hanya borrower atau pemilik barang "
                    "yang boleh membuat jadwal COD."
                )

    def __str__(self):
        return (
            f"{self.get_schedule_type_display()} - "
            f"{self.loan_request}"
        )


class Place(models.Model):
    """Tempat publik dari OpenStreetMap, untuk rekomendasi titik COD."""

    osm_id = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=200, db_index=True)
    address = models.CharField(max_length=300, blank=True)
    kind = models.CharField(max_length=30, db_index=True)
    latitude = models.FloatField(db_index=True)
    longitude = models.FloatField(db_index=True)

    class Meta:
        indexes = [models.Index(fields=["latitude", "longitude"])]

    def __str__(self):
        return f"{self.name} ({self.kind})"


    
    
    