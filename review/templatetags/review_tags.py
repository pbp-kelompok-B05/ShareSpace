from django import template

from loans.models import LoanRequest
from review.models import Review
from review.reputation import get_reputation

register = template.Library()

LATEST_REVIEWS_ON_CARD = 3


@register.inclusion_tag("review/partials/reputation_card.html")
def reputation_card(target_user):
    """Kartu reputasi untuk halaman profil (modul authentication).

    Pakai:
        {% load review_tags %}
        {% reputation_card target_user %}

    Berisi Trust Score, level, rata-rata rating, sebaran bintang, dan 3 ulasan terbaru.
    """
    return {
        "target_user": target_user,
        "reputation": get_reputation(target_user),
        "latest_reviews": Review.objects.visible()
        .filter(reviewee=target_user)
        .select_related("reviewer")[:LATEST_REVIEWS_ON_CARD],
    }


@register.inclusion_tag("review/partials/review_action.html", takes_context=True)
def review_action(context, loan):
    """Tombol ulasan untuk halaman detail transaksi.

    Pakai di template modul loans:
        {% load review_tags %}
        {% review_action loan %}

    Menampilkan "Beri ulasan" jika transaksi selesai dan user belum mengulas, tautan ubah
    jika sudah, dan tidak menampilkan apa pun untuk orang luar atau transaksi yang belum selesai.
    """
    user = context["request"].user
    is_party = user.is_authenticated and user.pk in (loan.borrower_id, loan.item.owner_id)
    if not is_party or loan.status != LoanRequest.Status.COMPLETED:
        return {"show": False}
    return {
        "show": True,
        "loan": loan,
        "existing": Review.objects.filter(loan=loan, reviewer=user).first(),
    }
