from django.shortcuts import render

# Create your views here.

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.core.exceptions import ValidationError

from loans.models import LoanRequest
from .models import CODLocation, PickupSchedule
from .forms import CODLocationForm, PickupScheduleForm
import logging

logger = logging.getLogger(__name__)



# Di views.py: HAPUS semua kode pencarian Overpass/Nominatim lama
# (OVERPASS_ENDPOINTS, _run_overpass, _nominatim, _search_*, overpass_search lama, dst.),
# lalu pakai kode ini. Pastikan import di bagian atas file:
import math

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Place


KIND_BY_CATEGORY = {
    "library": ["library"],
    "cafe": ["cafe"],
    "park": ["park"],
    "community": ["community_centre"],
    "minimarket": ["convenience", "supermarket"],
    "mall": ["mall"],
    "ibadah": ["place_of_worship"],
}

# kategori yang tidak ikut "Semua Lokasi" (jumlahnya sangat banyak)
EXCLUDED_FROM_ALL = KIND_BY_CATEGORY["minimarket"] + KIND_BY_CATEGORY["ibadah"]


def _distance_m(lat1, lon1, lat2, lon2):
    """Jarak haversine dalam meter."""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@require_GET
def overpass_search(request):
    try:
        lat = float(request.GET["lat"])
        lon = float(request.GET["lon"])
        radius = int(request.GET.get("radius", 1000))
    except (KeyError, ValueError):
        return JsonResponse({"message": "Parameter tidak valid."}, status=400)

    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 100 <= radius <= 5000):
        return JsonResponse({"message": "Parameter tidak valid."}, status=400)

    category = request.GET.get("category", "all")
    keyword = request.GET.get("keyword", "").strip()[:50]

    if category != "all" and category not in KIND_BY_CATEGORY:
        return JsonResponse({"message": "Kategori tidak valid."}, status=400)

    if not Place.objects.exists():
        return JsonResponse(
            {"message": "Data lokasi belum diimpor. Jalankan: python manage.py import_places <file>"},
            status=503,
        )

    # saring kotak di database dulu, lalu hitung jarak sebenarnya
    d_lat = radius / 111320
    d_lon = radius / (111320 * max(math.cos(math.radians(lat)), 0.01))

    qs = Place.objects.filter(
        latitude__range=(lat - d_lat, lat + d_lat),
        longitude__range=(lon - d_lon, lon + d_lon),
    )
    if category == "all":
        qs = qs.exclude(kind__in=EXCLUDED_FROM_ALL)
    else:
        qs = qs.filter(kind__in=KIND_BY_CATEGORY[category])
    if keyword:
        qs = qs.filter(name__icontains=keyword)

    found = []
    for p in qs[:500]:
        dist = _distance_m(lat, lon, p.latitude, p.longitude)
        if dist <= radius:
            found.append((dist, {
                "id": p.osm_id,
                "name": p.name,
                "address": p.address or "Alamat belum tersedia",
                "latitude": p.latitude,
                "longitude": p.longitude,
                "type": p.kind,
            }))

    found.sort(key=lambda item: item[0])
    return JsonResponse({"places": [item for _, item in found[:50]]})

# HELPER FUNCTIONS

def form_errors(form):
    return JsonResponse({
        "success": False,
        "errors": form.errors.get_json_data(),
    }, status=400)


def location_to_dict(location):
    return {
        "id": str(location.pk),
        "name": location.name,
        "address": location.address,
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "notes": location.notes,
        "created_by": str(location.created_by_id),
    }


def schedule_to_dict(schedule):
    return {
        "id": str(schedule.pk),
        "loan_request": str(schedule.loan_request_id),
        "cod_location": str(schedule.cod_location_id),
        "location_name": schedule.cod_location.name,
        "schedule_type": schedule.schedule_type,
        "schedule_type_label": schedule.get_schedule_type_display(),
        "scheduled_time": schedule.scheduled_time.isoformat(),
        "notes": schedule.notes,
    }


def user_can_access_loan(user, loan):
    return (
        user.is_superuser
        or loan.borrower_id == user.pk
        or loan.item.owner_id == user.pk
    )


def get_accessible_loan(request, loan_id):
    loans = LoanRequest.objects.select_related(
        "item", "item__owner"
    )
    
    if not request.user.is_superuser:
        loans = loans.filter(
            Q(borrower=request.user)
            | Q(item__owner=request.user)
        )

    return get_object_or_404(loans, pk=loan_id)


# HALAMAN PETA COD

@login_required
@require_GET
def cod_map_page(request):
    return render(
        request,
        "cod_location/location_list.html"
    )


# CRUD COD LOCATION

@login_required
@require_GET
def location_list(request):
    locations = CODLocation.objects.select_related(
        "created_by"
    ).all()

    return JsonResponse({
        "success": True,
        "locations": [
            location_to_dict(location)
            for location in locations
        ],
    })


@login_required
@require_GET
def location_detail(request, pk):
    location = get_object_or_404(CODLocation, pk=pk)

    return JsonResponse({
        "success": True,
        "location": location_to_dict(location),
    })

@login_required
@require_POST
def location_create(request):
    form = CODLocationForm(request.POST)

    if not form.is_valid():
        return form_errors(form)

    location = form.save(commit=False)
    location.created_by = request.user

    try:
        location.full_clean()
        location.save()

    except ValidationError as e:
        return JsonResponse({
            "success": False,
            "message": "Data lokasi tidak valid.",
            "errors": (
                e.message_dict
                if hasattr(e, "message_dict")
                else {"__all__": e.messages}
            ),
        }, status=400)

    return JsonResponse({
        "success": True,
        "message": "Lokasi COD berhasil ditambahkan.",
        "location": location_to_dict(location),
    }, status=201)


@login_required
@require_POST
def location_update(request, pk):
    location = get_object_or_404(CODLocation, pk=pk)

    if (
        location.created_by_id != request.user.pk
        and not request.user.is_staff
    ):
        return JsonResponse({
            "success": False,
            "message": "Tidak memiliki izin mengubah lokasi.",
        }, status=403)

    form = CODLocationForm(
        request.POST,
        instance=location,
    )

    if not form.is_valid():
        return form_errors(form)

    location = form.save(commit=False)

    try:
        location.full_clean()
        location.save()

    except ValidationError as e:
        return JsonResponse({
            "success": False,
            "message": "Data lokasi tidak valid.",
            "errors": (
                e.message_dict
                if hasattr(e, "message_dict")
                else {"__all__": e.messages}
            ),
        }, status=400)

    return JsonResponse({
        "success": True,
        "message": "Lokasi COD berhasil diperbarui.",
        "location": location_to_dict(location),
    })


@login_required
@require_POST
def location_delete(request, pk):
    location = get_object_or_404(CODLocation, pk=pk)

    if (
        location.created_by_id != request.user.pk
        and not request.user.is_staff
    ):
        return JsonResponse({
            "success": False,
            "message": "Tidak memiliki izin menghapus lokasi.",
        }, status=403)

    if location.pickup_schedules.exists():
        return JsonResponse({
            "success": False,
            "message": "Lokasi masih digunakan dalam jadwal COD.",
        }, status=409)

    location.delete()

    return JsonResponse({
        "success": True,
        "message": "Lokasi COD berhasil dihapus.",
    })


# CRUD PICKUP SCHEDULE

@login_required
@require_GET
def schedule_list(request, loan_id):
    loan = get_accessible_loan(request, loan_id)

    schedules = PickupSchedule.objects.filter(
        loan_request=loan
    ).select_related("cod_location")

    return JsonResponse({
        "success": True,
        "schedules": [
            schedule_to_dict(schedule)
            for schedule in schedules
        ],
    })

@login_required
@require_GET
def schedule_detail(request, pk):
    schedule = get_object_or_404(
        PickupSchedule.objects.select_related(
            "loan_request__item",
            "cod_location",
        ),
        pk=pk,
    )

    if not user_can_access_loan(
        request.user, schedule.loan_request
    ):
        return JsonResponse({
            "success": False,
            "message": "Tidak memiliki akses ke jadwal.",
        }, status=403)

    return JsonResponse({
        "success": True,
        "schedule": schedule_to_dict(schedule),
    })

@login_required
@require_POST
def schedule_create(request, loan_id):
    loan = get_accessible_loan(request, loan_id)

    if loan.status not in [
        LoanRequest.Status.PENDING,
        LoanRequest.Status.APPROVED,
        LoanRequest.Status.BORROWED,
    ]:
        return JsonResponse({
            "success": False,
            "message": "Status transaksi tidak mengizinkan penjadwalan.",
        }, status=400)

    form = PickupScheduleForm(request.POST)

    if not form.is_valid():
        return form_errors(form)

    schedule = form.save(commit=False)
    schedule.loan_request = loan
    schedule.created_by = request.user

    try:
        schedule.full_clean()

        with transaction.atomic():
            schedule.save()

    except ValidationError as e:
        return JsonResponse({
            "success": False,
            "message": "Data jadwal tidak valid atau jadwal sudah ada.",
            "errors": (
                e.message_dict
                if hasattr(e, "message_dict")
                else {"__all__": e.messages}
            ),
        }, status=400)

    except IntegrityError:
        return JsonResponse({
            "success": False,
            "message": "Jadwal untuk jenis ini sudah ada.",
        }, status=409)

    return JsonResponse({
        "success": True,
        "message": "Jadwal COD berhasil dibuat.",
        "schedule": schedule_to_dict(schedule),
    }, status=201)


@login_required
@require_POST
def schedule_update(request, pk):
    schedule = get_object_or_404(
        PickupSchedule.objects.select_related(
            "loan_request__item",
            "cod_location",
        ),
        pk=pk,
    )

    loan = schedule.loan_request

    if not user_can_access_loan(request.user, loan):
        return JsonResponse({
            "success": False,
            "message": "Tidak memiliki izin mengubah jadwal.",
        }, status=403)

    if loan.status not in [
        LoanRequest.Status.PENDING,
        LoanRequest.Status.APPROVED,
        LoanRequest.Status.BORROWED,
    ]:
        return JsonResponse({
            "success": False,
            "message": "Jadwal transaksi ini tidak dapat diubah.",
        }, status=400)

    form = PickupScheduleForm(
        request.POST,
        instance=schedule,
    )

    if not form.is_valid():
        return form_errors(form)

    schedule = form.save(commit=False)

    try:
        schedule.full_clean()

        with transaction.atomic():
            schedule.save()

    except ValidationError as e:
        return JsonResponse({
            "success": False,
            "message": "Data jadwal tidak valid atau jenis jadwal sudah digunakan.",
            "errors": (
                e.message_dict
                if hasattr(e, "message_dict")
                else {"__all__": e.messages}
            ),
        }, status=400)

    except IntegrityError:
        return JsonResponse({
            "success": False,
            "message": "Jenis jadwal tersebut sudah digunakan.",
        }, status=409)

    return JsonResponse({
        "success": True,
        "message": "Jadwal berhasil diperbarui.",
        "schedule": schedule_to_dict(schedule),
    })


@login_required
@require_POST
def schedule_delete(request, pk):
    schedule = get_object_or_404(
        PickupSchedule.objects.select_related(
            "loan_request__item"
        ),
        pk=pk,
    )

    loan = schedule.loan_request

    if not user_can_access_loan(request.user, loan):
        return JsonResponse({
            "success": False,
            "message": "Tidak memiliki izin menghapus jadwal.",
        }, status=403)

    if loan.status not in [
        LoanRequest.Status.PENDING,
        LoanRequest.Status.APPROVED,
    ]:
        return JsonResponse({
            "success": False,
            "message": "Jadwal transaksi ini tidak dapat dihapus.",
        }, status=400)

    schedule.delete()

    return JsonResponse({
        "success": True,
        "message": "Jadwal berhasil dihapus.",
    })
    
@login_required
@require_GET
def schedule_manage_page(request, loan_id):
    loan = get_accessible_loan(request, loan_id)

    return render(
        request,
        "cod_location/schedule_manage.html",
        {
            "loan": loan,
        }
    )


    
    
    
    
