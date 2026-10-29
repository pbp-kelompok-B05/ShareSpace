"""View ulasan transaksi (CRUD Review) untuk pengguna."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from loans.models import LoanRequest
from review.forms import ReviewForm
from review.htmx import render_list
from review.models import Review

REVIEWS_PER_PAGE = 10
PENDING_LOANS_LIMIT = 5
TABS = ("written", "received")


def _get_own_review(request, pk):
    review = get_object_or_404(Review.objects.select_related("reviewee", "loan__item"), pk=pk)
    if review.reviewer_id != request.user.pk:
        raise PermissionDenied("Kamu hanya dapat mengelola ulasan milikmu sendiri.")
    if not review.is_editable_by(request.user):
        raise PermissionDenied("Ulasan ini disembunyikan admin sehingga tidak dapat diubah.")
    return review


def _render_form(request, form, review, is_create):
    return render(request, "review/review_form.html", {
        "form": form,
        "review": review,
        "is_create": is_create,
        "rating_choices": ReviewForm.RATING_CHOICES,
    })


@login_required
@require_http_methods(["GET", "POST"])
def review_create(request, loan_id):
    loan = get_object_or_404(
        LoanRequest.objects.select_related("borrower", "item", "item__owner"), pk=loan_id
    )
    if request.user.pk not in (loan.borrower_id, loan.item.owner_id):
        raise PermissionDenied("Hanya pihak dalam transaksi ini yang dapat memberi ulasan.")
    if loan.status != LoanRequest.Status.COMPLETED:
        raise PermissionDenied("Ulasan hanya dapat diberikan setelah transaksi selesai.")

    existing = Review.objects.filter(loan=loan, reviewer=request.user).first()
    if existing:
        messages.info(request, "Kamu sudah memberi ulasan untuk transaksi ini. Silakan ubah ulasanmu.")
        return redirect("review:review_update", pk=existing.pk)

    review = Review.for_loan(loan, request.user)
    form = ReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ulasan berhasil dikirim. Terima kasih!")
        return redirect("loans:detail", pk=loan.pk)
    return _render_form(request, form, review, is_create=True)


@login_required
@require_http_methods(["GET", "POST"])
def review_update(request, pk):
    review = _get_own_review(request, pk)
    form = ReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ulasan berhasil diperbarui.")
        return redirect("review:my_reviews")
    return _render_form(request, form, review, is_create=False)


@login_required
@require_http_methods(["GET", "POST"])
def review_delete(request, pk):
    review = _get_own_review(request, pk)
    if request.method == "POST":
        review.delete()
        messages.success(request, "Ulasan dihapus.")
        return redirect("review:my_reviews")
    return render(request, "review/review_confirm_delete.html", {"review": review})


@login_required
def my_reviews(request):
    tab = request.GET.get("tab", "written")
    if tab not in TABS:
        tab = "written"

    if tab == "written":
        reviews = Review.objects.filter(reviewer=request.user).select_related("reviewee", "loan__item")
    else:
        # Ulasan yang disembunyikan admin tidak ditampilkan ke pihak yang dinilai.
        reviews = Review.objects.visible().filter(reviewee=request.user).select_related(
            "reviewer", "loan__item"
        )

    # Transaksi selesai yang belum kamu ulas, untuk mengingatkan pengguna.
    pending_loans = list(
        LoanRequest.objects.filter(status=LoanRequest.Status.COMPLETED)
        .filter(Q(borrower=request.user) | Q(item__owner=request.user))
        .exclude(reviews__reviewer=request.user)
        .select_related("item")
        .order_by("-updated_at")[:PENDING_LOANS_LIMIT]
    )

    page_obj = Paginator(reviews, REVIEWS_PER_PAGE).get_page(request.GET.get("page"))
    context = {"tab": tab, "page_obj": page_obj, "pending_loans": pending_loans}
    return render_list(
        request, "review/my_reviews.html", "review/partials/my_review_list.html", context
    )
