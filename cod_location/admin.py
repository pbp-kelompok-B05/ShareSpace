from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import CODLocation, PickupSchedule


@admin.register(CODLocation)
class CODLocationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "address",
        "latitude",
        "longitude",
        "created_by",
    )
    search_fields = ("name", "address")


@admin.register(PickupSchedule)
class PickupScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "loan_request",
        "schedule_type",
        "cod_location",
        "scheduled_time",
        "created_by",
    )
    list_filter = ("schedule_type",)
    search_fields = ("notes", "cod_location__name")