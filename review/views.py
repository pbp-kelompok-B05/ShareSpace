from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from items.models import Item
from loans.models import LoanRequest
from review.forms import ReportForm
from review.htmx import render_list
from review.models import Report

User = get_user_model()

REPORTS_PER_PAGE = 10
TARGET_RELATED = Report.TARGET_RELATED


def _get_own_report(request, pk, editable=False):
    """Ambil laporan milik user; editable=True juga mensyaratkan status Menunggu."""
    report = get_object_or_404(Report, pk=pk)
    if report.reporter_id != request.user.pk:
        raise PermissionDenied("Kamu hanya dapat mengelola laporan milikmu sendiri.")
    if editable and not report.is_editable_by(request.user):
        raise PermissionDenied("Laporan yang sudah ditinjau admin tidak dapat diubah.")
    return report


def _create_report(request, target):
    """Alur bersama pembuatan laporan untuk target barang maupun pengguna."""
    active = Report.objects.filter(
        reporter=request.user, status__in=Report.ACTIVE_STATUSES, **target
    ).first()
    if active:
        messages.info(request, "Kamu masih punya laporan aktif untuk target ini.")
        return redirect("review:report_detail", pk=active.pk)

    report = Report(reporter=request.user, **target)
    form = ReportForm(request.POST or None, instance=report)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Laporan berhasil dikirim dan akan ditinjau admin.")
        return redirect("review:report_detail", pk=report.pk)

    return render(request, "review/report_form.html", {
        "form": form, "report": report, "is_create": True,
    })


@login_required
@require_http_methods(["GET", "POST"])
def report_item_create(request, item_id):
    item = get_object_or_404(Item.objects.select_related("owner"), pk=item_id)
    if item.owner_id == request.user.pk:
        raise PermissionDenied("Kamu tidak dapat melaporkan barang milikmu sendiri.")
    return _create_report(request, {"target_item": item})


@login_required
@require_http_methods(["GET", "POST"])
def report_user_create(request, username):
    target_user = get_object_or_404(User, username=username, is_active=True)
    if target_user.pk == request.user.pk:
        raise PermissionDenied("Kamu tidak dapat melaporkan dirimu sendiri.")
    return _create_report(request, {"target_user": target_user})


@login_required
@require_http_methods(["GET", "POST"])
def report_loan_create(request, loan_id):
    loan = get_object_or_404(
        LoanRequest.objects.select_related("item", "item__owner", "borrower"), pk=loan_id
    )
    if request.user.pk not in (loan.borrower_id, loan.item.owner_id):
        raise PermissionDenied("Hanya pihak dalam transaksi ini yang dapat melaporkannya.")
    if loan.status not in Report.REPORTABLE_LOAN_STATUSES:
        raise PermissionDenied("Transaksi ini belum dapat dilaporkan.")
    return _create_report(request, {"target_loan": loan})


@login_required
def my_reports(request):
    reports = Report.objects.filter(reporter=request.user).select_related(*TARGET_RELATED)
    current_status = request.GET.get("status", "")
    if current_status not in Report.Status.values:
        current_status = ""
    if current_status:
        reports = reports.filter(status=current_status)

    page_obj = Paginator(reports, REPORTS_PER_PAGE).get_page(request.GET.get("page"))
    context = {
        "page_obj": page_obj,
        "current_status": current_status,
        "statuses": Report.Status.choices,
    }
    # HTMX (filter/pagination) cukup menerima isi daftar; history-restore tetap halaman penuh.
    return render_list(
        request, "review/my_reports.html", "review/partials/my_report_list.html", context
    )


@login_required
def report_detail(request, pk):
    report = get_object_or_404(
        Report.objects.select_related("reporter", "target_item__owner", *TARGET_RELATED), pk=pk
    )
    if report.reporter_id != request.user.pk and not request.user.is_staff:
        raise PermissionDenied("Kamu tidak punya akses ke laporan ini.")
    return render(request, "review/report_detail.html", {
        "report": report,
        "can_edit": report.is_editable_by(request.user),
    })


@login_required
@require_http_methods(["GET", "POST"])
def report_update(request, pk):
    report = _get_own_report(request, pk, editable=True)
    form = ReportForm(request.POST or None, instance=report)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Laporan berhasil diperbarui.")
        return redirect("review:report_detail", pk=report.pk)
    return render(request, "review/report_form.html", {
        "form": form, "report": report, "is_create": False,
    })


@login_required
@require_http_methods(["GET", "POST"])
def report_delete(request, pk):
    report = _get_own_report(request, pk, editable=True)
    if request.method == "POST":
        report.delete()
        messages.success(request, "Laporan dibatalkan.")
        return redirect("review:my_reports")
    return render(request, "review/report_confirm_delete.html", {"report": report})
