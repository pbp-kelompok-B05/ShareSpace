from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from items.models import Item
from loans.models import LoanRequest
from loans.recaptcha import verify_recaptcha
from loans.serializers import LoanRequestSerializer

# Transactions accessible to the current user
def _loan_queryset(user):
    return LoanRequest.objects.filter(
        Q(borrower=user) | Q(item__owner=user)
    ).select_related(
        "item", "item__owner", "item__owner__userprofile", "borrower", "borrower__userprofile"
    ).order_by("-created_at", "-pk")

# Lock Item before LoanRequest inside transaction.atomic()
def _lock_loan(request, pk):
    visible_loan = get_object_or_404(_loan_queryset(request.user), pk=pk)
    item = get_object_or_404(Item.all_objects.select_for_update(), pk=visible_loan.item_id)
    loan = get_object_or_404(LoanRequest.objects.select_for_update(), pk=visible_loan.pk)
    loan.item = item

    return loan, item

# Loan list and create API
@api_view(["GET", "HEAD", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def loan_list(request):
    if request.method in ("GET", "HEAD"):
        role = request.query_params.get("role", "borrower")
        status_query = request.query_params.get("status", "")
        loans = _loan_queryset(request.user)

        if role not in ("borrower", "lender"):
            return Response({"role": ["Pilih borrower atau lender."]}, status=status.HTTP_400_BAD_REQUEST)

        if role == "borrower":
            loans = loans.filter(borrower=request.user)
        else:
            loans = loans.filter(item__owner=request.user)

        if status_query:
            if status_query not in LoanRequest.Status.values:
                return Response({"status": ["Status tidak valid."]}, status=status.HTTP_400_BAD_REQUEST)
            loans = loans.filter(status=status_query)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(loans, request)
        serializer = LoanRequestSerializer(page, many=True, context={"request": request})

        return paginator.get_paginated_response(serializer.data)

    serializer = LoanRequestSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)

    if not settings.RECAPTCHA_SITE_KEY or not settings.RECAPTCHA_SECRET_KEY:
        return Response({"detail": "reCAPTCHA belum dikonfigurasi."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    token = request.data.get("g-recaptcha-response", "")
    if not isinstance(token, str) or not token.strip() or not verify_recaptcha(token.strip()):
        return Response({"detail": "Verifikasi reCAPTCHA gagal. Silakan coba lagi."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        item = get_object_or_404(
            Item.objects.select_for_update(), pk=serializer.validated_data["item"].pk, owner__is_active=True
        )

        if item.owner_id == request.user.pk:
            return Response({"detail": "Tidak bisa meminjam barang sendiri."}, status=status.HTTP_403_FORBIDDEN)

        has_active_loan = LoanRequest.objects.filter(
            item=item, status__in=[LoanRequest.Status.APPROVED, LoanRequest.Status.BORROWED]
        ).exists()

        if not item.is_available or has_active_loan:
            return Response({"detail": "Barang tidak tersedia untuk dipinjam."}, status=status.HTTP_409_CONFLICT)

        if LoanRequest.objects.filter(borrower=request.user, item=item, status=LoanRequest.Status.PENDING).exists():
            return Response({"detail": "Kamu sudah mengajukan barang ini."}, status=status.HTTP_409_CONFLICT)

        serializer.save(borrower=request.user, item=item)

    return Response(serializer.data, status=status.HTTP_201_CREATED)

# Loan detail and update API
@api_view(["GET", "HEAD", "PATCH"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def loan_detail(request, pk):
    if request.method in ("GET", "HEAD"):
        loan = get_object_or_404(_loan_queryset(request.user), pk=pk)
        serializer = LoanRequestSerializer(loan, context={"request": request})

        return Response(serializer.data)

    with transaction.atomic():
        loan, _ = _lock_loan(request, pk)

        if loan.borrower_id != request.user.pk:
            return Response({"detail": "Hanya peminjam yang dapat mengubah pengajuan."}, status=status.HTTP_403_FORBIDDEN)

        if loan.status != LoanRequest.Status.PENDING:
            return Response({"detail": "Transaksi tidak dapat diubah."}, status=status.HTTP_409_CONFLICT)

        serializer = LoanRequestSerializer(loan, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

    return Response(serializer.data)

# Shared status transition logic for authenticated action APIs
def _transition(request, pk, role, expected_status, target_status=None, returning=False):
    try:
        with transaction.atomic():
            loan, item = _lock_loan(request, pk)
            actor_id = loan.borrower_id if role == "borrower" else item.owner_id

            if actor_id != request.user.pk:
                return Response({"detail": "Tidak memiliki akses melakukan tindakan ini."}, status=status.HTTP_403_FORBIDDEN)

            if loan.status != expected_status:
                return Response({"detail": "Status transaksi sudah berubah. Muat ulang data."}, status=status.HTTP_409_CONFLICT)

            if returning:
                if loan.return_requested_at:
                    return Response({"detail": "Pengembalian sudah diajukan."}, status=status.HTTP_409_CONFLICT)
                loan.return_requested_at = timezone.now()

            if target_status == LoanRequest.Status.APPROVED:
                if item.is_deleted or not item.is_available:
                    return Response({"detail": "Barang tidak tersedia."}, status=status.HTTP_409_CONFLICT)
                item.is_available = False
                item.save(update_fields=["is_available", "updated_at"])

            if target_status == LoanRequest.Status.COMPLETED:
                if not loan.return_requested_at:
                    return Response({"detail": "Peminjam belum mengajukan pengembalian."}, status=status.HTTP_409_CONFLICT)
                item.is_available = not item.is_deleted
                item.save(update_fields=["is_available", "updated_at"])

            if target_status is not None:
                loan.status = target_status

            loan.save(update_fields=["status", "return_requested_at", "updated_at"])

            if target_status == LoanRequest.Status.APPROVED:
                LoanRequest.objects.filter(item=item, status=LoanRequest.Status.PENDING).exclude(pk=loan.pk).update(
                    status=LoanRequest.Status.REJECTED, updated_at=timezone.now()
                )

    except IntegrityError:
        return Response({"detail": "Barang sudah memiliki peminjaman aktif."}, status=status.HTTP_409_CONFLICT)

    serializer = LoanRequestSerializer(loan, context={"request": request})

    return Response(serializer.data)

# Cancel loan API
@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def loan_cancel(request, pk):
    return _transition(request, pk, "borrower", LoanRequest.Status.PENDING, LoanRequest.Status.CANCELLED)

# Approve loan API
@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def loan_approve(request, pk):
    return _transition(request, pk, "lender", LoanRequest.Status.PENDING, LoanRequest.Status.APPROVED)

# Reject loan API
@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def loan_reject(request, pk):
    return _transition(request, pk, "lender", LoanRequest.Status.PENDING, LoanRequest.Status.REJECTED)

# Mark loan borrowed API
@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def loan_mark_borrowed(request, pk):
    return _transition(request, pk, "lender", LoanRequest.Status.APPROVED, LoanRequest.Status.BORROWED)

# Request return API
@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def loan_request_return(request, pk):
    return _transition(request, pk, "borrower", LoanRequest.Status.BORROWED, returning=True)

# Complete loan API
@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def loan_complete(request, pk):
    return _transition(request, pk, "lender", LoanRequest.Status.BORROWED, LoanRequest.Status.COMPLETED)