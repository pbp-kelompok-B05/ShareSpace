from django.db import models

# Create your models here.

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class CODLocation(models.Model):
    name = models.CharField(max_length=150)
    address = models.TextField()
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_cod_locations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# class PickupSchedule(models.Model):
#     # loan_request = models.OneToOneField(
#     #     "loans.LoanRequest",
#     #     on_delete=models.CASCADE,
#     #     related_name="pickup_schedule",
#     # )
#     cod_location = models.ForeignKey(
#         CODLocation,
#         on_delete=models.PROTECT,
#         related_name="pickup_schedules",
#     )
#     pickup_time = models.DateTimeField()
#     return_time = models.DateTimeField()
#     notes = models.TextField(blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         ordering = ["pickup_time"]

#     def clean(self):
#         from django.core.exceptions import ValidationError

#         super().clean()

#         if (
#             self.pickup_time
#             and self.return_time
#             and self.return_time <= self.pickup_time
#         ):
#             raise ValidationError({
#                 "return_time": (
#                     "Jadwal pengembalian harus setelah waktu pengambilan."
#                 )
#             })

#     def __str__(self):
#         return f"Jadwal transaksi #{self.loan_request_id}"
