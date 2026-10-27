import json
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from review.forms import ModerationForm
from review.htmx import is_htmx, render_list
from review.models import Report

REPORTS_PER_PAGE = 15
SEARCH_MAX_LENGTH = 100


def staff_required(view_func):
    """Wajib login (redirect ke halaman login), lalu wajib staff (403 bersama)."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Halaman ini khusus admin ShareSpace.")
        return view_func(request, *args, **kwargs)

    return wrapper


def _toast(response, message, level):
    response["HX-Trigger"] = json.dumps({"showToast": {"message": message, "level": level}})
    return response


def _safe_next(request):
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return reverse("review:report_list")


@staff_required
def report_list(request):
    reports = Report.objects.select_related("reporter", "target_item", "target_user")

    current_status = request.GET.get("status", "")
    if current_status not in Report.Status.values:
        current_status = ""
    current_reason = request.GET.get("reason", "")
    if current_reason not in Report.Reason.values:
        current_reason = ""
    query = request.GET.get("q", "").strip()[:SEARCH_MAX_LENGTH]

    if current_status:
        reports = reports.filter(status=current_status)
    if current_reason:
        reports = reports.filter(reason=current_reason)
    if query:
        reports = reports.filter(
            Q(reporter__username__icontains=query)
            | Q(target_user__username__icontains=query)
            | Q(target_item__name__icontains=query)
            | Q(description__icontains=query)
        )

    # Satu query agregat untuk semua ringkasan status, terlepas dari filter aktif.
    status_counts = Report.objects.aggregate(
        **{status: Count("pk", filter=Q(status=status)) for status in Report.Status.values}
    )
    page_obj = Paginator(reports, REPORTS_PER_PAGE).get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "current_status": current_status,
        "current_reason": current_reason,
        "query": query,
        "statuses": Report.Status.choices,
        "reasons": Report.Reason.choices,
        "status_counts": status_counts,
        "status_summary": [
            (value, label, status_counts[value]) for value, label in Report.Status.choices
        ],
        "next_url": request.get_full_path(),
    }
    return render_list(
        request, "review/report_list.html", "review/partials/moderation_list.html", context
    )


@staff_required
@require_POST
def report_moderate(request, pk):
    report = get_object_or_404(
        Report.objects.select_related("reporter", "target_item", "target_user"), pk=pk
    )
    form = ModerationForm(request.POST)
    try:
        if not form.is_valid():
            raise ValidationError("Data moderasi tidak valid.")
        status = form.cleaned_data["status"]
        # Catatan yang tidak dikirim berarti tidak diubah; dikirim kosong berarti dihapus.
        note = form.cleaned_data["admin_note"] if "admin_note" in request.POST else None
        if status:
            report.transition_to(status, note=note)
            message = f"Status laporan diubah ke {report.get_status_display()}."
        elif note is not None:
            report.admin_note = note
            report.save(update_fields=["admin_note", "updated_at"])
            message = "Catatan admin disimpan."
        else:
            raise ValidationError("Tidak ada perubahan yang dikirim.")
    except ValidationError as error:
        if is_htmx(request):
            return _toast(HttpResponse(status=400), error.messages[0], "error")
        messages.error(request, error.messages[0])
        return redirect(_safe_next(request))

    if is_htmx(request):
        response = render(request, "review/partials/moderation_row.html", {
            "report": report, "next_url": _safe_next(request),
        })
        return _toast(response, message, "success")
    messages.success(request, message)
    return redirect(_safe_next(request))
