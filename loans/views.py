from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from .models import LoanRequest
from .forms import LoanRequestForm
from items.models import Item

# Create your views here.

@login_required(login_url="/login/")
def loan_list(request):
    return render(request, "loan_list.html")

@login_required(login_url="/login/")
def loan_list_data(request):
    status = request.GET.get("status", "")

    if status and status not in LoanRequest.Status.values:
        return JsonResponse({"error": "Status tidak valid"}, status=400)

    loans = LoanRequest.objects.filter(borrower=request.user).select_related("item")

    if status:
        loans = loans.filter(status=status)

    data = []
    for loan in loans:
        data.append(
            {
                "id": str(loan.pk),
                "item_name": str(loan.item),
                "status": loan.status,
                "status_label": loan.get_status_display(),
                "start_date": loan.start_date.isoformat(),
                "due_date": loan.due_date.isoformat(),
                "detail_url": reverse("loans:detail", args=[loan.pk]),
            }
        )

    return JsonResponse({"loans": data})

@login_required(login_url="/login/")
def loan_create(request, item_id):
    item = get_object_or_404(Item, pk=item_id)

    if item.owner_id == request.user.pk:
        return JsonResponse({"success": False, "message": "Tidak bisa meminjam barang sendiri."}, status=403)

    if not item.is_verified and not item.is_available:
        return JsonResponse({"success": False, "message": "Barang tidak dapat dipinjam."}, status=403)

    form = LoanRequestForm(request.POST)
    if request.method == "POST" and form.is_valid():
        loan = form.save(commit=False)
        loan.borrower = request.user
        loan.item = item
        loan.save()

        return JsonResponse({
            "succes": True,
            "message": "Permintaan peminjaman berhasil dibuat.",
            "pk": str(loan.pk),
            "detail_url": reverse("loans:detail", args=[loan.pk]),
        }, status=201)

    return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

@login_required(login_url="/login/")
def loan_detail(request, pk):
    loans = LoanRequest.objects.select_related("borrower", "item", "item__owner").filter(
        Q(borrower=request.user) | Q(item__owner=request.user)
    )
    loan = get_object_or_404(loan, pk=pk)

    return render(request, "loan_detail.html", {"loan": loan})