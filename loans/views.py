
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from .models import LoanRequest
from .forms import LoanRequestForm
from items.models import Item

LOGIN_URL = "authentication:login"


# Borrower loan list
@login_required(login_url=LOGIN_URL)
def loan_list(request):
    borrower_count = LoanRequest.objects.filter(borrower=request.user).count()
    lender_count = LoanRequest.objects.filter(item__owner=request.user).count()

    return render(request, "loan_list.html", {
        "role": "borrower",
        "borrower_count": borrower_count,
        "lender_count": lender_count,
    })


# Lender loan list
@login_required(login_url=LOGIN_URL)
def loan_lender_list(request):
    borrower_count = LoanRequest.objects.filter(borrower=request.user).count()
    lender_count = LoanRequest.objects.filter(item__owner=request.user).count()

    return render(request, "loan_list.html", {
        "role": "lender",
        "borrower_count": borrower_count,
        "lender_count": lender_count,
    })


# Borrower loan list AJAX
@login_required(login_url=LOGIN_URL)
def loan_list_data(request):
    status = request.GET.get("status", "")

    if status and status not in LoanRequest.Status.values:
        return JsonResponse({"error": "Status tidak valid."}, status=400)

    loans = LoanRequest.objects.filter(borrower=request.user).select_related(
        "item", "item__owner", "item__owner__userprofile"
    )

    if status:
        loans = loans.filter(status=status)

    data = []
    for loan in loans:
        owner = loan.item.owner
        profile = getattr(owner, "userprofile", None)
        owner_name = profile.full_name.strip() if profile and profile.full_name.strip() else owner.username
        phone = profile.phone_number.strip() if profile else ""
        contact_url = "tel:" + phone if phone else ("mailto:" + owner.email if owner.email else None)

        data.append({
            "id": str(loan.pk),
            "item_name": loan.item.name,
            "image_url": loan.item.image_url,
            "person_label": "Pemilik",
            "person_name": owner_name,
            "contact_url": contact_url,
            "status": loan.status,
            "status_label": loan.get_status_display(),
            "start_date": loan.start_date.isoformat(),
            "due_date": loan.due_date.isoformat(),
            "return_requested": loan.return_requested_at is not None,
            "detail_url": reverse("loans:detail", args=[loan.pk]),
            "cancel_url": reverse("loans:cancel", args=[loan.pk])
                if loan.status == LoanRequest.Status.PENDING else None,
            "return_url": reverse("loans:request_return", args=[loan.pk])
                if loan.status == LoanRequest.Status.BORROWED and not loan.return_requested_at else None,
        })

    return JsonResponse({"loans": data})


# Lender loan list AJAX
@login_required(login_url=LOGIN_URL)
def loan_lender_list_data(request):
    status = request.GET.get("status", "")

    if status and status not in LoanRequest.Status.values:
        return JsonResponse({"error": "Status tidak valid."}, status=400)

    loans = LoanRequest.objects.filter(item__owner=request.user).select_related(
        "item", "borrower", "borrower__userprofile"
    )

    if status:
        loans = loans.filter(status=status)

    data = []
    for loan in loans:
        borrower = loan.borrower
        profile = getattr(borrower, "userprofile", None)
        borrower_name = profile.full_name.strip() if profile and profile.full_name.strip() else borrower.username
        phone = profile.phone_number.strip() if profile else ""
        contact_url = "tel:" + phone if phone else ("mailto:" + borrower.email if borrower.email else None)

        data.append({
            "id": str(loan.pk),
            "item_name": loan.item.name,
            "image_url": loan.item.image_url,
            "person_label": "Peminjam",
            "person_name": borrower_name,
            "contact_url": contact_url,
            "status": loan.status,
            "status_label": loan.get_status_display(),
            "start_date": loan.start_date.isoformat(),
            "due_date": loan.due_date.isoformat(),
            "return_requested": loan.return_requested_at is not None,
            "detail_url": reverse("loans:detail", args=[loan.pk]),
            "approve_url": reverse("loans:approve", args=[loan.pk]) if loan.status == LoanRequest.Status.PENDING else None,
            "reject_url": reverse("loans:reject", args=[loan.pk]) if loan.status == LoanRequest.Status.PENDING else None,
            "borrowed_url": reverse("loans:mark_borrowed", args=[loan.pk]) if loan.status == LoanRequest.Status.APPROVED else None,
            "complete_url": reverse("loans:complete", args=[loan.pk]) if loan.status == LoanRequest.Status.BORROWED and loan.return_requested_at else None,
        })

    return JsonResponse({"loans": data})

# Create loan
@login_required(login_url=LOGIN_URL)
def loan_create(request, item_id):
    if request.method != "POST":
        return JsonResponse({"message": "Method tidak diizinkan."}, status=405)

    form = LoanRequestForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    with transaction.atomic():
        item = get_object_or_404(Item.objects.select_for_update(), pk=item_id)

        if item.owner_id == request.user.pk:
            return JsonResponse({"message": "Tidak bisa meminjam barang sendiri."}, status=403)

        if not item.is_verified or not item.is_available:
            return JsonResponse({"message": "Barang tidak tersedia untuk dipinjam."}, status=409)

        if LoanRequest.objects.filter(borrower=request.user, item=item, status=LoanRequest.Status.PENDING).exists():
            return JsonResponse({"message": "Kamu sudah mengajukan barang ini."}, status=409)

        loan = form.save(commit=False)
        loan.borrower = request.user
        loan.item = item
        loan.save()

    return JsonResponse({
        "success": True,
        "message": "Permintaan peminjaman berhasil dibuat.",
        "detail_url": reverse("loans:detail", args=[loan.pk]),
    }, status=201)


# Loan detail
@login_required(login_url=LOGIN_URL)
def loan_detail(request, pk):
    loans = LoanRequest.objects.select_related("borrower", "item", "item__owner").filter(
        Q(borrower=request.user) | Q(item__owner=request.user)
    )
    loan = get_object_or_404(loans, pk=pk)

    is_borrower = loan.borrower_id == request.user.pk
    is_lender = loan.item.owner_id == request.user.pk

    form = None
    if is_borrower and loan.status == LoanRequest.Status.PENDING:
        form = LoanRequestForm(instance=loan)

    return render(request, "loan_detail.html", {
        "loan": loan,
        "form": form,
        "is_borrower": is_borrower,
        "is_lender": is_lender,
        "can_manage": is_lender and loan.status == LoanRequest.Status.PENDING,
        "can_handover": is_lender and loan.status == LoanRequest.Status.APPROVED,
        "can_request_return": is_borrower and loan.status == LoanRequest.Status.BORROWED
            and loan.return_requested_at is None,
        "can_complete": is_lender and loan.status == LoanRequest.Status.BORROWED
            and loan.return_requested_at is not None,
    })


# Update loan AJAX
@login_required(login_url=LOGIN_URL)
def loan_update(request, pk):
    if request.method != "POST":
        return JsonResponse({"message": "Method tidak diizinkan."}, status=405)

    with transaction.atomic():
        loan = get_object_or_404(LoanRequest.objects.select_for_update(), pk=pk)

        if loan.borrower_id != request.user.pk:
            return JsonResponse({"message": "Tidak memiliki akses mengubah transaksi."}, status=403)

        if loan.status != LoanRequest.Status.PENDING:
            return JsonResponse({"message": "Transaksi tidak dapat diubah."}, status=409)

        form = LoanRequestForm(request.POST, instance=loan)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

        form.save()

    return JsonResponse({"message": "Pengajuan berhasil diperbarui."}, status=200)


# Cancel loan AJAX
@login_required(login_url=LOGIN_URL)
def loan_cancel(request, pk):
    if request.method != "POST":
        return JsonResponse({"message": "Method tidak diizinkan."}, status=405)

    with transaction.atomic():
        loan = get_object_or_404(LoanRequest.objects.select_for_update(), pk=pk)

        if loan.borrower_id != request.user.pk:
            return JsonResponse({"message": "Tidak memiliki akses membatalkan transaksi."}, status=403)

        if loan.status != LoanRequest.Status.PENDING:
            return JsonResponse({"message": "Transaksi tidak dapat dibatalkan."}, status=409)

        loan.status = LoanRequest.Status.CANCELLED
        loan.save()

    return JsonResponse({"message": "Pengajuan berhasil dibatalkan."}, status=200)


# Approve loan AJAX
@login_required(login_url=LOGIN_URL)
def loan_approve(request, pk):
    if request.method != "POST":
        return JsonResponse({"message": "Method tidak diizinkan."}, status=405)

    item_id = get_object_or_404(LoanRequest, pk=pk).item_id

    try:
        with transaction.atomic():
            item = get_object_or_404(Item.all_objects.select_for_update(), pk=item_id)
            loan = get_object_or_404(LoanRequest.objects.select_for_update(), pk=pk)

            if item.owner_id != request.user.pk:
                return JsonResponse({"message": "Hanya pemilik yang dapat menyetujui."}, status=403)

            if loan.status != LoanRequest.Status.PENDING:
                return JsonResponse({"message": "Status transaksi sudah berubah."}, status=409)

            if item.is_deleted or not item.is_verified or not item.is_available:
                return JsonResponse({"message": "Barang tidak tersedia."}, status=409)

            loan.status = LoanRequest.Status.APPROVED
            loan.save()
            item.is_available = False
            item.save()

    except IntegrityError:
        return JsonResponse({"message": "Barang sudah memiliki peminjaman aktif."}, status=409)

    return JsonResponse({"message": "Pengajuan berhasil disetujui."}, status=200)


# Reject loan AJAX
@login_required(login_url=LOGIN_URL)
def loan_reject(request, pk):
    if request.method != "POST":
        return JsonResponse({"message": "Method tidak diizinkan."}, status=405)

    with transaction.atomic():
        loan = get_object_or_404(LoanRequest.objects.select_for_update(), pk=pk)

        if loan.item.owner_id != request.user.pk:
            return JsonResponse({"message": "Hanya pemilik yang dapat menolak."}, status=403)

        if loan.status != LoanRequest.Status.PENDING:
            return JsonResponse({"message": "Status transaksi sudah berubah."}, status=409)

        loan.status = LoanRequest.Status.REJECTED
        loan.save()

    return JsonResponse({"message": "Pengajuan berhasil ditolak."}, status=200)


# Mark loan borrowed AJAX
@login_required(login_url=LOGIN_URL)
def loan_mark_borrowed(request, pk):
    if request.method != "POST":
        return JsonResponse({"message": "Method tidak diizinkan."}, status=405)

    with transaction.atomic():
        loan = get_object_or_404(LoanRequest.objects.select_for_update(), pk=pk)

        if loan.item.owner_id != request.user.pk:
            return JsonResponse({"message": "Hanya pemilik yang dapat menyerahkan barang."}, status=403)

        if loan.status != LoanRequest.Status.APPROVED:
            return JsonResponse({"message": "Status transaksi sudah berubah."}, status=409)

        loan.status = LoanRequest.Status.BORROWED
        loan.save()

    return JsonResponse({"message": "Barang telah diserahkan kepada peminjam."}, status=200)


# Request return AJAX
@login_required(login_url=LOGIN_URL)
def loan_request_return(request, pk):
    if request.method != "POST":
        return JsonResponse({"message": "Method tidak diizinkan."}, status=405)

    with transaction.atomic():
        loan = get_object_or_404(LoanRequest.objects.select_for_update(), pk=pk)

        if loan.borrower_id != request.user.pk:
            return JsonResponse({"message": "Hanya peminjam yang dapat mengajukan pengembalian."}, status=403)

        if loan.status != LoanRequest.Status.BORROWED or loan.return_requested_at:
            return JsonResponse({"message": "Permintaan pengembalian tidak dapat diproses."}, status=409)

        loan.return_requested_at = timezone.now()
        loan.save()

    return JsonResponse({"message": "Pengembalian diajukan. Menunggu konfirmasi pemilik."}, status=200)


# Complete loan AJAX
@login_required(login_url=LOGIN_URL)
def loan_complete(request, pk):
    if request.method != "POST":
        return JsonResponse({"message": "Method tidak diizinkan."}, status=405)

    item_id = get_object_or_404(LoanRequest, pk=pk).item_id

    with transaction.atomic():
        item = get_object_or_404(Item.all_objects.select_for_update(), pk=item_id)
        loan = get_object_or_404(LoanRequest.objects.select_for_update(), pk=pk)

        if item.owner_id != request.user.pk:
            return JsonResponse({"message": "Hanya pemilik yang dapat menyelesaikan transaksi."}, status=403)

        if loan.status != LoanRequest.Status.BORROWED:
            return JsonResponse({"message": "Status transaksi sudah berubah."}, status=409)

        if not loan.return_requested_at:
            return JsonResponse({"message": "Peminjam belum mengajukan pengembalian."}, status=409)

        loan.status = LoanRequest.Status.COMPLETED
        loan.save()
        item.is_available = not item.is_deleted
        item.save()

    return JsonResponse({"message": "Pengembalian dikonfirmasi. Transaksi selesai."}, status=200)
