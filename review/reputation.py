"""Reputasi pengguna: rata-rata rating, sebaran bintang, dan Trust Score 0–100.

Rumus Trust Score (dihitung ulang setiap kali, tidak disimpan di database):

    rating_bayes = (C * PRIOR + rata_rata * n) / (C + n)        # n = jumlah ulasan
    poin_rating  = 70 * (rating_bayes - 1) / 4                    # skala 1–5 → 0–70
    poin_aktif   = 30 * min(transaksi_selesai, 20) / 20           # 0–30
    skor         = poin_rating + poin_aktif - 10 * laporan_terbukti, dibatasi 0–100

Rata-rata bayesian menarik rating ke nilai netral (3,5) selama ulasan masih sedikit,
sehingga satu ulasan bintang 5 tidak langsung memberi skor sempurna dan satu ulasan
bintang 1 tidak langsung menjatuhkan skor. Pengguna tanpa transaksi dan ulasan diberi
label "Pengguna baru" alih-alih skor 0.
"""
from dataclasses import dataclass

from django.db.models import Avg, Count, Q

from loans.models import LoanRequest
from review.models import Report, Review

PRIOR_RATING = 3.5
PRIOR_WEIGHT = 3
RATING_POINTS = 70
ACTIVITY_POINTS = 30
ACTIVITY_CAP = 20
REPORT_PENALTY = 10


@dataclass(frozen=True)
class TrustLevel:
    key: str
    label: str


# Urut dari ambang tertinggi; skor >= ambang mendapat level tersebut.
TRUST_LEVELS = (
    (85, TrustLevel("excellent", "Sangat terpercaya")),
    (70, TrustLevel("trusted", "Terpercaya")),
    (50, TrustLevel("fair", "Cukup terpercaya")),
    (0, TrustLevel("low", "Perlu perhatian")),
)
NEW_USER_LEVEL = TrustLevel("new", "Pengguna baru")


def trust_score(average_rating, review_count, completed_count, resolved_report_count=0):
    """Trust Score bulat 0–100, atau None untuk pengguna baru (tanpa transaksi dan ulasan)."""
    if review_count < 0 or completed_count < 0 or resolved_report_count < 0:
        raise ValueError("Jumlah tidak boleh negatif.")
    if review_count and average_rating is None:
        raise ValueError("average_rating wajib diisi jika ada ulasan.")
    if average_rating is not None and not Review.MIN_RATING <= average_rating <= Review.MAX_RATING:
        raise ValueError("average_rating harus di antara 1 dan 5.")
    if review_count == 0 and completed_count == 0:
        return None

    rating_sum = (average_rating or 0) * review_count
    bayes = (PRIOR_WEIGHT * PRIOR_RATING + rating_sum) / (PRIOR_WEIGHT + review_count)
    rating_points = RATING_POINTS * (bayes - Review.MIN_RATING) / (Review.MAX_RATING - Review.MIN_RATING)
    activity_points = ACTIVITY_POINTS * min(completed_count, ACTIVITY_CAP) / ACTIVITY_CAP
    score = rating_points + activity_points - REPORT_PENALTY * resolved_report_count
    return round(min(100, max(0, score)))


def trust_level(score):
    if score is None:
        return NEW_USER_LEVEL
    for threshold, level in TRUST_LEVELS[:-1]:
        if score >= threshold:
            return level
    return TRUST_LEVELS[-1][1]


@dataclass(frozen=True)
class StarCount:
    stars: int
    count: int
    percent: int


@dataclass(frozen=True)
class Reputation:
    average_rating: float | None
    review_count: int
    completed_count: int
    resolved_report_count: int
    distribution: list
    score: int | None
    level: TrustLevel

    @property
    def average_display(self):
        """Rata-rata satu desimal dengan koma (mis. "4,5"), atau "–" jika belum ada ulasan."""
        if self.average_rating is None:
            return "–"
        return f"{self.average_rating:.1f}".replace(".", ",")

    @property
    def rounded_average(self):
        """Rata-rata dibulatkan untuk tampilan bintang (partials/stars.html)."""
        return round(self.average_rating) if self.average_rating is not None else 0


def get_reputation(user):
    """Reputasi lengkap satu pengguna dalam tiga query agregat."""
    star_range = range(Review.MAX_RATING, Review.MIN_RATING - 1, -1)
    # Query 1: rata-rata, jumlah, dan sebaran bintang ulasan yang tampil.
    stats = Review.objects.visible().filter(reviewee=user).aggregate(
        average=Avg("rating"),
        total=Count("pk"),
        **{f"stars_{stars}": Count("pk", filter=Q(rating=stars)) for stars in star_range},
    )
    # Query 2: transaksi selesai sebagai peminjam maupun pemilik.
    completed = LoanRequest.objects.filter(
        Q(borrower=user) | Q(item__owner=user), status=LoanRequest.Status.COMPLETED
    ).count()
    # Query 3: laporan terbukti (Selesai) terhadap pengguna, barang miliknya, atau transaksi
    # tempat ia menjadi pihak lawan pelapor.
    against_loan = (Q(target_loan__borrower=user) | Q(target_loan__item__owner=user)) & ~Q(reporter=user)
    resolved_reports = Report.objects.filter(
        Q(target_user=user) | Q(target_item__owner=user) | against_loan,
        status=Report.Status.RESOLVED,
    ).count()

    total = stats["total"]
    average = round(stats["average"], 2) if stats["average"] is not None else None
    distribution = [
        StarCount(stars, stats[f"stars_{stars}"],
                  round(100 * stats[f"stars_{stars}"] / total) if total else 0)
        for stars in star_range
    ]
    score = trust_score(stats["average"], total, completed, resolved_reports)
    return Reputation(
        average_rating=average,
        review_count=total,
        completed_count=completed,
        resolved_report_count=resolved_reports,
        distribution=distribution,
        score=score,
        level=trust_level(score),
    )
