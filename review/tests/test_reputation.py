from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from items.models import Item
from loans.models import LoanRequest
from review.models import Report, Review
from review.reputation import get_reputation, trust_level, trust_score
from review.tests.test_review_models import ReviewTestMixin

User = get_user_model()


class TrustScoreFormulaTest(SimpleTestCase):
    """Rumus murni: 70% rating bayesian + 30% aktivitas - 10 per laporan terbukti."""

    def test_new_user_has_no_score(self):
        self.assertIsNone(trust_score(average_rating=None, review_count=0, completed_count=0))

    def test_reviewed_but_no_completed_still_scored(self):
        # Ulasan selalu berasal dari transaksi selesai, tapi fungsi tetap aman.
        self.assertIsNotNone(trust_score(average_rating=4, review_count=1, completed_count=0))

    def test_completed_without_reviews_uses_neutral_prior(self):
        # Prior 3.5 → 43.75 poin rating; 5/20 transaksi → 7.5 poin aktivitas.
        self.assertEqual(trust_score(average_rating=None, review_count=0, completed_count=5), 51)

    def test_known_values(self):
        cases = [
            # (rata-rata, jumlah ulasan, transaksi selesai, laporan terbukti) -> skor
            ((5, 20, 20, 0), 97),  # bayes 4.80 → 66.6 + 30
            ((5, 1, 1, 0), 52),    # bayes 3.875 → 50.3 + 1.5
            ((1, 1, 1, 0), 34),    # bayes 2.875 → 32.8 + 1.5
            ((4, 10, 10, 0), 65),  # bayes 3.885 → 50.5 + 15
        ]
        for (average, reviews, completed, reports), expected in cases:
            with self.subTest(average=average, reviews=reviews, completed=completed):
                self.assertEqual(
                    trust_score(average, reviews, completed, resolved_report_count=reports),
                    expected,
                )

    def test_single_perfect_review_is_far_from_top_score(self):
        one = trust_score(5, 1, 1)
        many = trust_score(5, 20, 20)
        self.assertLess(one, 60)
        self.assertGreater(many, 90)

    def test_completed_count_is_capped_at_twenty(self):
        self.assertEqual(trust_score(4, 5, 20), trust_score(4, 5, 200))

    def test_each_resolved_report_costs_ten_points(self):
        base = trust_score(5, 20, 20)
        self.assertEqual(trust_score(5, 20, 20, resolved_report_count=2), base - 20)

    def test_score_never_below_zero(self):
        self.assertEqual(trust_score(1, 3, 1, resolved_report_count=50), 0)

    def test_score_never_above_hundred(self):
        self.assertLessEqual(trust_score(5, 10_000, 10_000), 100)

    def test_higher_rating_never_lowers_score(self):
        scores = [trust_score(rating, 5, 5) for rating in (1, 2, 3, 4, 5)]
        self.assertEqual(scores, sorted(scores))

    def test_more_completed_never_lowers_score(self):
        scores = [trust_score(4, 5, completed) for completed in (1, 5, 10, 20)]
        self.assertEqual(scores, sorted(scores))

    def test_invalid_inputs_rejected(self):
        for kwargs in (
            {"average_rating": 6, "review_count": 1, "completed_count": 1},
            {"average_rating": 0, "review_count": 1, "completed_count": 1},
            {"average_rating": 4, "review_count": -1, "completed_count": 1},
            {"average_rating": 4, "review_count": 1, "completed_count": -2},
            {"average_rating": None, "review_count": 3, "completed_count": 3},
        ):
            with self.subTest(**kwargs):
                with self.assertRaises(ValueError):
                    trust_score(**kwargs)

    def test_trust_levels(self):
        cases = [
            (None, "new"), (100, "excellent"), (85, "excellent"), (84, "trusted"),
            (70, "trusted"), (69, "fair"), (50, "fair"), (49, "low"), (0, "low"),
        ]
        for score, key in cases:
            with self.subTest(score=score):
                self.assertEqual(trust_level(score).key, key)

    def test_trust_level_labels(self):
        self.assertEqual(trust_level(None).label, "Pengguna baru")
        self.assertEqual(trust_level(90).label, "Sangat terpercaya")


class GetReputationTest(ReviewTestMixin, TestCase):
    def review(self, reviewer, rating, loan=None, **kwargs):
        return self.make_review(loan=loan or self.make_loan(), reviewer=reviewer, rating=rating, **kwargs)

    def test_new_user(self):
        reputation = get_reputation(self.outsider)
        self.assertIsNone(reputation.score)
        self.assertEqual(reputation.level.key, "new")
        self.assertEqual(reputation.review_count, 0)
        self.assertIsNone(reputation.average_rating)

    def test_average_and_count_use_visible_received_reviews_only(self):
        self.review(self.borrower, 5)
        self.review(self.borrower, 3)
        self.review(self.borrower, 1, is_hidden=True)
        self.review(self.lender, 2)  # ulasan untuk borrower, bukan lender
        reputation = get_reputation(self.lender)
        self.assertEqual(reputation.review_count, 2)
        self.assertEqual(reputation.average_rating, 4.0)

    def test_completed_count_includes_both_roles(self):
        self.make_loan()  # lender sebagai pemilik
        other_item = Item.objects.create(
            owner=self.borrower, name="Tenda Kemah",
            description="Tenda kemah kapasitas empat orang, lengkap dengan pasak.",
            category=Item.Category.OUTDOOR, condition=Item.Condition.GOOD,
        )
        LoanRequest.objects.create(
            borrower=self.lender, item=other_item, status=LoanRequest.Status.COMPLETED,
            start_date=date.today() - timedelta(days=4), due_date=date.today() - timedelta(days=1),
        )
        self.make_loan(status=LoanRequest.Status.REJECTED)
        self.assertEqual(get_reputation(self.lender).completed_count, 2)

    def test_resolved_reports_about_user_or_their_items_are_penalised(self):
        self.review(self.borrower, 5)
        before = get_reputation(self.lender).score
        Report.objects.create(
            reporter=self.borrower, target_user=self.lender, reason=Report.Reason.MISCONDUCT,
            description="Pemilik bersikap kasar saat serah terima COD.", status=Report.Status.RESOLVED,
        )
        Report.objects.create(
            reporter=self.outsider, target_item=self.item, reason=Report.Reason.ITEM_MISMATCH,
            description="Barang tidak sesuai dengan foto di katalog.", status=Report.Status.RESOLVED,
        )
        Report.objects.create(
            reporter=self.outsider, target_user=self.lender, reason=Report.Reason.OTHER,
            description="Laporan yang ditolak admin karena tidak terbukti.", status=Report.Status.REJECTED,
        )
        reputation = get_reputation(self.lender)
        self.assertEqual(reputation.resolved_report_count, 2)
        self.assertEqual(reputation.score, before - 20)

    def test_rating_distribution(self):
        for rating in (5, 5, 4, 1):
            self.review(self.borrower, rating)
        distribution = {row.stars: row for row in get_reputation(self.lender).distribution}
        self.assertEqual([row.stars for row in get_reputation(self.lender).distribution], [5, 4, 3, 2, 1])
        self.assertEqual(distribution[5].count, 2)
        self.assertEqual(distribution[5].percent, 50)
        self.assertEqual(distribution[3].count, 0)
        self.assertEqual(distribution[3].percent, 0)

    def test_uses_three_queries(self):
        self.review(self.borrower, 4)
        with self.assertNumQueries(3):
            get_reputation(self.lender)
