import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.urls import reverse

from items.models import Item
from loans.models import LoanRequest
from review.models import Report
from review.reputation import get_reputation
from review.tests.test_review_models import ReviewTestMixin

HTMX = {"HTTP_HX_REQUEST": "true"}
DESCRIPTION = "Barang dikembalikan terlambat tiga hari tanpa kabar sama sekali."


class LoanReportMixin(ReviewTestMixin):
    def fresh_loan(self, status=LoanRequest.Status.COMPLETED):
        """Loan dengan barang baru milik lender (loans membatasi satu loan aktif per barang)."""
        item = Item.objects.create(
            owner=self.lender, name=f"Kamera {uuid.uuid4().hex[:6]}",
            description="Kamera mirrorless lengkap dengan baterai cadangan dan tas.",
            category=self.item.category, condition=self.item.condition,
        )
        return self.make_loan(status=status, item=item)

    def make_loan_report(self, loan=None, reporter=None, **kwargs):
        report = Report(
            reporter=reporter or self.lender,
            target_loan=loan or self.make_loan(),
            reason=kwargs.pop("reason", Report.Reason.LATE_RETURN),
            description=kwargs.pop("description", DESCRIPTION),
            **kwargs,
        )
        report.full_clean()
        report.save()
        return report


class LoanReportModelTest(LoanReportMixin, TestCase):
    def test_party_can_report_loan(self):
        report = self.make_loan_report()
        self.assertEqual(report.target_type, "loan")
        self.assertEqual(report.target, report.target_loan)

    def test_accused_user_is_the_other_party(self):
        loan = self.make_loan()
        self.assertEqual(self.make_loan_report(loan, reporter=self.lender).accused_user, self.borrower)
        self.assertEqual(self.make_loan_report(loan, reporter=self.borrower).accused_user, self.lender)

    def test_accused_user_for_item_and_user_targets(self):
        item_report = Report(reporter=self.borrower, target_item=self.item)
        user_report = Report(reporter=self.lender, target_user=self.borrower)
        self.assertEqual(item_report.accused_user, self.lender)
        self.assertEqual(user_report.accused_user, self.borrower)

    def test_outsider_cannot_report_loan(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_loan_report(reporter=self.outsider)
        self.assertIn("target_loan", ctx.exception.message_dict)

    def test_reportable_statuses(self):
        allowed = {LoanRequest.Status.APPROVED, LoanRequest.Status.BORROWED, LoanRequest.Status.COMPLETED}
        for status in LoanRequest.Status:
            with self.subTest(status=status):
                loan = self.fresh_loan(status)
                if status in allowed:
                    self.make_loan_report(loan)
                else:
                    with self.assertRaises(ValidationError):
                        self.make_loan_report(loan)

    def test_existing_report_stays_valid_if_loan_status_changes(self):
        loan = self.fresh_loan(LoanRequest.Status.BORROWED)
        report = self.make_loan_report(loan)
        LoanRequest.objects.filter(pk=loan.pk).update(status=LoanRequest.Status.CANCELLED)
        report.refresh_from_db()
        report.description = DESCRIPTION + " Ditambah detail."
        report.full_clean()

    def test_loan_and_user_together_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Report.objects.create(
                reporter=self.lender, target_loan=self.make_loan(), target_user=self.borrower,
                reason=Report.Reason.OTHER, description=DESCRIPTION,
            )

    def test_one_active_report_per_loan_per_reporter(self):
        loan = self.make_loan()
        self.make_loan_report(loan)
        with self.assertRaises(ValidationError):
            self.make_loan_report(loan)
        # Pihak lain tetap boleh melapor transaksi yang sama.
        self.make_loan_report(loan, reporter=self.borrower)

    def test_closed_report_allows_new_one(self):
        loan = self.make_loan()
        self.make_loan_report(loan, status=Report.Status.REJECTED)
        self.make_loan_report(loan)

    def test_loan_protected_from_deletion(self):
        report = self.make_loan_report()
        with self.assertRaises(Exception):
            report.target_loan.delete()


class LoanReportReputationTest(LoanReportMixin, TestCase):
    def test_resolved_loan_report_penalises_accused_not_reporter(self):
        loan = self.make_loan()
        self.make_loan_report(loan, reporter=self.lender, status=Report.Status.RESOLVED)
        self.assertEqual(get_reputation(self.borrower).resolved_report_count, 1)
        self.assertEqual(get_reputation(self.lender).resolved_report_count, 0)

    def test_unresolved_loan_report_not_penalised(self):
        self.make_loan_report(reporter=self.borrower, status=Report.Status.REVIEWING)
        self.assertEqual(get_reputation(self.lender).resolved_report_count, 0)

    def test_still_three_queries(self):
        self.make_loan_report(status=Report.Status.RESOLVED)
        with self.assertNumQueries(3):
            get_reputation(self.borrower)


class LoanReportViewTest(LoanReportMixin, TestCase):
    def setUp(self):
        self.loan = self.fresh_loan(LoanRequest.Status.BORROWED)
        self.url = reverse("review:report_loan_create", args=[self.loan.pk])
        self.client.force_login(self.lender)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(
            response, f"{reverse('authentication:login')}?next={self.url}", fetch_redirect_response=False
        )

    def test_form_shows_loan_and_other_party(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transaksi")
        self.assertContains(response, self.loan.item.name)
        self.assertContains(response, self.borrower.username)

    def test_creates_loan_report(self):
        response = self.client.post(self.url, {"reason": Report.Reason.LATE_RETURN, "description": DESCRIPTION})
        report = Report.objects.get(target_loan=self.loan)
        self.assertRedirects(response, reverse("review:report_detail", args=[report.pk]),
                             fetch_redirect_response=False)
        self.assertEqual(report.reporter, self.lender)
        self.assertIsNone(report.target_user_id)
        self.assertIsNone(report.target_item_id)

    def test_posted_targets_ignored(self):
        self.client.post(self.url, {
            "reason": Report.Reason.OTHER, "description": DESCRIPTION,
            "target_user": self.outsider.pk, "target_item": self.item.pk, "status": "resolved",
        })
        report = Report.objects.get(target_loan=self.loan)
        self.assertIsNone(report.target_user_id)
        self.assertEqual(report.status, Report.Status.PENDING)

    def test_outsider_forbidden(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(
            self.client.post(self.url, {"reason": "other", "description": DESCRIPTION}).status_code, 403
        )
        self.assertFalse(Report.objects.exists())

    def test_unreportable_status_forbidden(self):
        loan = self.fresh_loan(LoanRequest.Status.PENDING)
        response = self.client.get(reverse("review:report_loan_create", args=[loan.pk]))
        self.assertEqual(response.status_code, 403)

    def test_unknown_loan_404(self):
        response = self.client.get(reverse("review:report_loan_create", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_active_report_redirects_to_detail(self):
        report = self.make_loan_report(self.loan)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("review:report_detail", args=[report.pk]),
                             fetch_redirect_response=False)

    def test_detail_and_my_reports_show_loan_target(self):
        report = self.make_loan_report(self.loan)
        for url in (reverse("review:report_detail", args=[report.pk]), reverse("review:my_reports")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "Transaksi")
                self.assertContains(response, self.loan.item.name)

    def test_my_reports_query_count_with_loan_reports(self):
        for _ in range(3):
            self.make_loan_report(self.make_loan())
        with self.assertNumQueries(4):
            self.client.get(reverse("review:my_reports"))


class LoanReportModerationTest(LoanReportMixin, TestCase):
    def setUp(self):
        self.admin = self.make_staff()
        self.client.force_login(self.admin)
        self.report = self.make_loan_report()

    def make_staff(self):
        return get_user_model().objects.create_user(
            username="reviewtest_admin", password="PasswordTest123.", is_staff=True
        )

    def test_dashboard_lists_loan_report_and_parties(self):
        response = self.client.get(reverse("review:report_list"))
        self.assertContains(response, "Transaksi")
        self.assertContains(response, self.item.name)

    def test_search_by_loan_item_or_party(self):
        url = reverse("review:report_list")
        for query in (self.item.name[:6], self.borrower.username):
            with self.subTest(q=query):
                response = self.client.get(url, {"q": query})
                self.assertIn(self.report, list(response.context["page_obj"]))

    def test_loan_reports_do_not_add_queries_to_dashboard(self):
        url = reverse("review:report_list")
        with self.assertNumQueries(5):
            self.client.get(url)
        self.make_loan_report(self.make_loan(), reporter=self.borrower)
        with self.assertNumQueries(5):
            self.client.get(url)

    def test_admin_changelist_shows_loan_target(self):
        self.admin.is_superuser = True
        self.admin.save()
        response = self.client.get(reverse("admin:review_report_changelist"))
        self.assertContains(response, self.item.name)


class LoanReportLinkTest(LoanReportMixin, TestCase):
    def render(self, user, loan):
        request = RequestFactory().get("/")
        request.user = user
        template = Template('{% include "review/partials/report_link.html" with loan=loan %}')
        return template.render(Context({"loan": loan, "user": user, "request": request}))

    def test_party_sees_report_link(self):
        loan = self.fresh_loan(LoanRequest.Status.BORROWED)
        html = self.render(self.borrower, loan)
        self.assertIn(reverse("review:report_loan_create", args=[loan.pk]), html)
        self.assertIn("Laporkan masalah", html)

    def test_hidden_for_outsider_and_unreportable_status(self):
        self.assertEqual(self.render(self.outsider, self.make_loan()).strip(), "")
        # Kondisi status di template harus sama dengan Report.REPORTABLE_LOAN_STATUSES.
        for status in LoanRequest.Status:
            with self.subTest(status=status):
                html = self.render(self.borrower, self.fresh_loan(status))
                self.assertEqual("Laporkan masalah" in html, status in Report.REPORTABLE_LOAN_STATUSES)
