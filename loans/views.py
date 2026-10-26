from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from .models import LoanRequest

# Create your views here.

@login_required
def loan_list(request):
    return render(request, "loan_list.html")

@login_required
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
            }
        )

    return JsonResponse({"loans": data})
