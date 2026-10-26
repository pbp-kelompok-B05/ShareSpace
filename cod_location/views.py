from django.shortcuts import render

# Create your views here.

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_GET, require_POST

from loans.models import LoanRequest
from .models import CODLocation, PickupSchedule
from .forms import CODLocationForm, PickupScheduleForm


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
        loan.borrower_id == user.pk
        or loan.item.owner_id == user.pk
    )


def get_accessible_loan(request, loan_id):
    loans = LoanRequest.objects.select_related(
        "item", "item__owner"
    ).filter(
        Q(borrower=request.user)
        | Q(item__owner=request.user)
    )

    return get_object_or_404(loans, pk=loan_id)


# HALAMAN PETA COD

@login_required(login_url="/login/")
@require_GET
def cod_map_page(request):
    return render(
        request,
        "cod_location/location_list.html"
    )


# CRUD COD LOCATION

@login_required(login_url="/login/")
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


@login_required(login_url="/login/")
@require_GET
def location_detail(request, pk):
    location = get_object_or_404(CODLocation, pk=pk)

    return JsonResponse({
        "success": True,
        "location": location_to_dict(location),
    })

@login_required(login_url="/login/")
@require_POST
def location_create(request):
    form = CODLocationForm(request.POST)

    if not form.is_valid():
        return form_errors(form)

    location = form.save(commit=False)
    location.created_by = request.user
    location.full_clean()
    location.save()

    return JsonResponse({
        "success": True,
        "message": "Lokasi COD berhasil ditambahkan.",
        "location": location_to_dict(location),
    }, status=201)


@login_required(login_url="/login/")
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
    location.full_clean()
    location.save()

    return JsonResponse({
        "success": True,
        "message": "Lokasi COD berhasil diperbarui.",
        "location": location_to_dict(location),
    })


@login_required(login_url="/login/")
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

@login_required(login_url="/login/")
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

@login_required(login_url="/login/")
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

@login_required(login_url="/login/")
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
    schedule.full_clean()

    try:
        with transaction.atomic():
            schedule.save()
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


@login_required(login_url="/login/")
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
    schedule.full_clean()

    try:
        with transaction.atomic():
            schedule.save()
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


@login_required(login_url="/login/")
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

