import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from authentication.models import UserProfile
from items.models import Item
from loans.models import LoanRequest

# Loan REST API tests
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class LoanRESTAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.owner = user.objects.create_user("api_owner", password="TestPass123!", email="owner@example.com")
        cls.borrower = user.objects.create_user("api_borrower", password="TestPass123!")
        cls.other = user.objects.create_user("api_other", password="TestPass123!")
        cls.item = Item.objects.create(
            owner=cls.owner, name="Kamera", description="Kamera untuk kegiatan mahasiswa.",
            category=Item.Category.ELECTRONICS, condition=Item.Condition.GOOD,
        )
        cls.start = timezone.localdate() + timedelta(days=2)
        cls.due = cls.start + timedelta(days=5)

    def url(self, action="list", loan=None):
        return reverse(f"loans_api:loan-{action}", args=[loan.pk] if loan else None)

    def data(self, **changes):
        data = {"item": self.item.pk, "start_date": self.start.isoformat(), "due_date": self.due.isoformat()}
        data.update(changes)

        return data

    def loan(self, **changes):
        data = {"item": self.item, "borrower": self.borrower, "start_date": self.start, "due_date": self.due}
        data.update(changes)

        return LoanRequest.objects.create(**data)

    def login_as(self, user):
        self.client.force_login(user)

    # Pengguna anonim mendapat respons JSON tanpa redirect ke halaman login.
    def test_anonymous_requests_are_json_errors_without_redirect(self):
        loan = self.loan()
        endpoints = [self.url(), self.url("detail", loan)]
        endpoints += [self.url(action, loan) for action in (
            "cancel", "approve", "reject", "mark-borrowed", "request-return", "complete",
        )]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response["Content-Type"], "application/json")
                self.assertNotIn("Location", response)

        self.assertEqual(self.client.post(self.url(), self.data(), format="json").status_code, 403)

    # Daftar transaksi sesuai peran dan filter status.
    def test_list_roles_status_and_pagination(self):
        mine = self.loan()
        self.loan(borrower=self.other, status=LoanRequest.Status.REJECTED)
        self.login_as(self.borrower)

        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(mine.pk))

        self.login_as(self.owner)
        response = self.client.get(self.url(), {"role": "lender", "status": "rejected"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], "rejected")
        self.assertEqual(self.client.get(self.url()).data["count"], 0)

    # Role atau status yang tidak dikenal ditolak.
    def test_bad_filters_return_400(self):
        self.login_as(self.borrower)

        for query in ({"role": "admin"}, {"status": "unknown"}):
            self.assertEqual(self.client.get(self.url(), query).status_code, 400)

    # Setiap halaman berisi maksimal 20 transaksi.
    def test_list_is_paginated(self):
        for _ in range(21):
            self.loan()

        self.login_as(self.borrower)
        first = self.client.get(self.url())
        self.assertEqual(first.data["count"], 21)
        self.assertEqual(len(first.data["results"]), 20)
        self.assertIsNotNone(first.data["next"])

        second = self.client.get(self.url(), {"page": 2})
        self.assertEqual(len(second.data["results"]), 1)

    # Detail, perubahan, dan aksi hanya dapat diakses peserta transaksi.
    def test_detail_only_for_participants(self):
        loan = self.loan()

        for user in (self.borrower, self.owner):
            self.login_as(user)
            self.assertEqual(self.client.get(self.url("detail", loan)).status_code, 200)

        self.login_as(self.other)
        self.assertEqual(self.client.get(self.url("detail", loan)).status_code, 404)

        response = self.client.patch(self.url("detail", loan), {"notes": "Tidak boleh"}, format="json")
        self.assertEqual(response.status_code, 404)

        for action in ("cancel", "approve", "reject", "mark-borrowed", "request-return", "complete"):
            self.assertEqual(self.client.post(self.url(action, loan)).status_code, 404)

    # UUID transaksi yang tidak ditemukan menghasilkan 404.
    def test_unknown_uuid_returns_404(self):
        self.login_as(self.borrower)

        response = self.client.get(reverse("loans_api:loan-detail", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)

    # Pengajuan menyimpan catatan serta menetapkan peminjam dan status dari server.
    def test_create_saves_json_and_ignores_forged_status_or_borrower(self):
        self.login_as(self.borrower)
        response = self.client.post(self.url(), self.data(
            notes="Untuk dokumentasi", borrower=self.owner.pk, status="completed",
        ), format="json")

        self.assertEqual(response.status_code, 201, response.data)

        loan = LoanRequest.objects.get(pk=response.data["id"])
        self.assertEqual(loan.borrower_id, self.borrower.pk)
        self.assertEqual(loan.status, "pending")
        self.assertEqual(loan.notes, "Untuk dokumentasi")
        self.assertEqual(response.data["available_actions"], ["edit", "cancel"])

    # API mobile tidak bergantung pada konfigurasi reCAPTCHA web.
    def test_create_without_recaptcha_configuration(self):
        self.login_as(self.borrower)

        with override_settings(RECAPTCHA_SITE_KEY="", RECAPTCHA_SECRET_KEY=""):
            response = self.client.post(self.url(), self.data(), format="json")

        self.assertEqual(response.status_code, 201, response.data)

    # Barang sendiri dan pengajuan pending ganda tidak diperbolehkan.
    def test_self_borrowing_and_duplicate_pending_are_rejected(self):
        self.login_as(self.owner)
        self.assertEqual(self.client.post(self.url(), self.data(), format="json").status_code, 403)

        self.login_as(self.borrower)
        self.loan()
        self.assertEqual(self.client.post(self.url(), self.data(), format="json").status_code, 409)

    # Barang tidak tersedia atau sudah memiliki transaksi aktif ditolak.
    def test_unavailable_item_or_existing_active_loan_returns_409(self):
        self.login_as(self.borrower)
        self.item.is_available = False
        self.item.save()
        self.assertEqual(self.client.post(self.url(), self.data(), format="json").status_code, 409)

        self.item.is_available = True
        self.item.save()
        self.loan(borrower=self.other, status=LoanRequest.Status.APPROVED)
        self.assertEqual(self.client.post(self.url(), self.data(), format="json").status_code, 409)

    # Barang terhapus dan barang milik akun nonaktif tidak bisa dipinjam.
    def test_deleted_item_and_inactive_owner_cannot_be_borrowed(self):
        self.login_as(self.borrower)
        self.item.soft_delete()
        self.assertEqual(self.client.post(self.url(), self.data(), format="json").status_code, 400)

        self.item.restore()
        self.owner.is_active = False
        self.owner.save()
        self.assertEqual(self.client.post(self.url(), self.data(), format="json").status_code, 400)

    # Validasi tanggal, field wajib.
    def test_date_validation_and_required_fields(self):
        self.login_as(self.borrower)
        bad_payloads = [
            self.data(start_date=(timezone.localdate() - timedelta(days=1)).isoformat()),
            self.data(due_date=(self.start - timedelta(days=1)).isoformat()),
            self.data(start_date="bad-date"),
            {"item": self.item.pk},
            self.data(due_date=None),
        ]

        for data in bad_payloads:
            with self.subTest(data=data):
                response = self.client.post(self.url(), data, format="json")
                self.assertEqual(response.status_code, 400)

        self.assertFalse(LoanRequest.objects.exists())

        response = self.client.post(self.url(), self.data(due_date=self.start.isoformat()), format="json")
        self.assertEqual(response.status_code, 201)

    # PATCH memvalidasi tanggal dan melindungi barang, peminjam, serta status.
    def test_patch_checks_both_dates_and_protects_item_and_status(self):
        loan = self.loan()
        self.login_as(self.borrower)
        response = self.client.patch(
            self.url("detail", loan), {"due_date": (self.start - timedelta(days=1)).isoformat()}, format="json"
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.patch(self.url("detail", loan), {
            "notes": "Catatan baru", "item": 999999, "status": "approved", "borrower": self.other.pk,
        }, format="json")

        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.notes, "Catatan baru")
        self.assertEqual(loan.item_id, self.item.pk)
        self.assertEqual(loan.borrower_id, self.borrower.pk)
        self.assertEqual(loan.status, "pending")

    # Catatan boleh diubah ketika tanggal mulai lama sudah lewat.
    def test_patch_allows_unchanged_past_date_but_not_new_past_date(self):
        loan = self.loan(start_date=timezone.localdate() - timedelta(days=2))
        self.login_as(self.borrower)

        response = self.client.patch(self.url("detail", loan), {"notes": "Masih pending"}, format="json")
        self.assertEqual(response.status_code, 200)

        response = self.client.patch(self.url("detail", loan), {
            "start_date": (timezone.localdate() - timedelta(days=1)).isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 400)

    # Hanya peminjam yang dapat mengedit dan membatalkan pengajuan pending.
    def test_only_borrower_can_edit_or_cancel_pending_loan(self):
        loan = self.loan()
        self.login_as(self.owner)

        response = self.client.patch(self.url("detail", loan), {"notes": "x"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post(self.url("cancel", loan)).status_code, 403)

        self.login_as(self.borrower)
        self.assertEqual(self.client.post(self.url("cancel", loan)).data["status"], "cancelled")
        self.assertEqual(self.client.post(self.url("cancel", loan)).status_code, 409)

        response = self.client.patch(self.url("detail", loan), {"notes": "x"}, format="json")
        self.assertEqual(response.status_code, 409)

    # Peminjam tidak boleh menjalankan aksi milik pemilik barang.
    def test_only_lender_can_approve_reject_handover_or_complete(self):
        loan = self.loan()
        self.login_as(self.borrower)

        for action in ("approve", "reject", "mark-borrowed", "complete"):
            self.assertEqual(self.client.post(self.url(action, loan)).status_code, 403)

    # Persetujuan menolak pengajuan lain dan membuat barang tidak tersedia.
    def test_approval_rejects_other_requests_and_blocks_second_approval(self):
        first = self.loan()
        second = self.loan(borrower=self.other)
        self.login_as(self.owner)

        self.assertEqual(self.client.post(self.url("approve", first)).status_code, 200)
        self.item.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(self.item.is_available)
        self.assertEqual(second.status, "rejected")
        self.assertEqual(self.client.post(self.url("approve", second)).status_code, 409)

    # Pengajuan tidak dapat disetujui jika barang terhapus atau tidak tersedia.
    def test_approval_rejects_deleted_or_unavailable_item(self):
        loan = self.loan()
        self.login_as(self.owner)
        self.item.soft_delete()
        self.assertEqual(self.client.post(self.url("approve", loan)).status_code, 409)

        self.item.restore()
        self.item.is_available = False
        self.item.save()
        self.assertEqual(self.client.post(self.url("approve", loan)).status_code, 409)

        loan.refresh_from_db()
        self.assertEqual(loan.status, "pending")

    # Pemilik dapat menolak pengajuan pending.
    def test_lender_can_reject(self):
        loan = self.loan()
        self.login_as(self.owner)

        response = self.client.post(self.url("reject", loan))
        self.assertEqual(response.data["status"], "rejected")

    # Alur lengkap dari pengajuan sampai barang tersedia kembali.
    def test_full_workflow_and_return_permissions(self):
        self.login_as(self.borrower)
        created = self.client.post(self.url(), self.data(), format="json")
        loan = LoanRequest.objects.get(pk=created.data["id"])

        self.login_as(self.owner)
        response = self.client.post(self.url("approve", loan))
        self.assertEqual(response.data["available_actions"], ["mark_borrowed"])

        response = self.client.post(self.url("mark-borrowed", loan))
        self.assertEqual(response.data["status"], "borrowed")
        self.assertEqual(self.client.post(self.url("complete", loan)).status_code, 409)
        self.assertEqual(self.client.post(self.url("request-return", loan)).status_code, 403)

        self.login_as(self.borrower)
        self.assertEqual(self.client.post(self.url("request-return", loan)).status_code, 200)
        self.assertEqual(self.client.post(self.url("request-return", loan)).status_code, 409)

        self.login_as(self.owner)
        response = self.client.post(self.url("complete", loan))
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["available_actions"], [])

        self.item.refresh_from_db()
        self.assertTrue(self.item.is_available)

    # Penyelesaian transaksi tidak mengaktifkan kembali barang yang terhapus.
    def test_completion_does_not_restore_deleted_item(self):
        self.item.is_available = False
        self.item.save()
        self.item.soft_delete(force=True)
        loan = self.loan(status=LoanRequest.Status.BORROWED, return_requested_at=timezone.now())
        self.login_as(self.owner)

        self.assertEqual(self.client.post(self.url("complete", loan)).status_code, 200)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_available)

    # Transisi yang tidak sesuai tidak mengubah status transaksi.
    def test_invalid_transitions_do_not_change_status(self):
        loan = self.loan()
        self.login_as(self.owner)

        for action in ("mark-borrowed", "complete"):
            self.assertEqual(self.client.post(self.url(action, loan)).status_code, 409)

        self.login_as(self.borrower)
        self.assertEqual(self.client.post(self.url("request-return", loan)).status_code, 409)

        loan.refresh_from_db()
        self.assertEqual(loan.status, "pending")

    # Kontak hanya ditampilkan selama transaksi approved atau borrowed.
    def test_contact_visible_only_during_active_loan(self):
        UserProfile.objects.create(user=self.owner, full_name="Pemilik Kamera", phone_number="0812345678")
        loan = self.loan()
        self.login_as(self.borrower)

        for state in LoanRequest.Status.values:
            loan.status = state
            loan.save()
            data = self.client.get(self.url("detail", loan)).data

            self.assertEqual(data["owner_name"], "Pemilik Kamera")
            expected = "tel:0812345678" if state in ("approved", "borrowed") else None
            self.assertEqual(data["contact_url"], expected)
            self.assertNotIn("email", data)

    # Data API muncul di web dan perubahan web terbaca melalui API.
    def test_api_changes_visible_on_web_and_web_changes_visible_on_api(self):
        self.login_as(self.borrower)
        created = self.client.post(self.url(), self.data(), format="json")
        loan = LoanRequest.objects.get(pk=created.data["id"])

        web = self.client.get(reverse("loans:detail", args=[loan.pk]))
        self.assertEqual(web.status_code, 200)
        self.assertEqual(web.context["loan"].pk, loan.pk)

        self.login_as(self.owner)
        response = self.client.post(reverse("loans:approve", args=[loan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(self.url("detail", loan)).data["status"], "approved")

    # POST dengan sesi login tetap membutuhkan token CSRF.
    def test_session_csrf_required_for_writes(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.borrower)

        self.assertEqual(client.get(self.url()).status_code, 200)
        self.assertEqual(client.post(self.url(), self.data(), format="json").status_code, 403)

        client.get(reverse("loans:list"))
        token = client.cookies["csrftoken"].value
        response = client.post(self.url(), self.data(), format="json", HTTP_X_CSRFTOKEN=token)

        self.assertEqual(response.status_code, 201, response.data)

    # Sesi pengguna yang dinonaktifkan tidak dapat mengakses API.
    def test_deactivated_session_cannot_access_api(self):
        self.login_as(self.borrower)
        self.borrower.is_active = False
        self.borrower.save()

        self.assertEqual(self.client.get(self.url()).status_code, 403)

    # DELETE, PUT, dan GET pada endpoint aksi tidak diperbolehkan.
    def test_delete_put_and_get_on_actions_are_not_allowed(self):
        loan = self.loan()
        self.login_as(self.borrower)

        self.assertEqual(self.client.delete(self.url("detail", loan)).status_code, 405)
        self.assertEqual(self.client.put(self.url("detail", loan), self.data(), format="json").status_code, 405)

        for action in ("cancel", "approve", "reject", "mark-borrowed", "request-return", "complete"):
            self.assertEqual(self.client.get(self.url(action, loan)).status_code, 405)

    # Pemilik hanya melihat transaksi untuk barang miliknya sendiri.
    def test_lender_list_excludes_transactions_for_other_owners(self):
        own_loan = self.loan()
        other_item = Item.objects.create(
            owner=self.other, name="Tripod", description="Tripod untuk dokumentasi kegiatan.",
            category=Item.Category.ELECTRONICS, condition=Item.Condition.GOOD,
        )
        self.loan(item=other_item)
        self.login_as(self.owner)

        response = self.client.get(self.url(), {"role": "lender"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(own_loan.pk))

    # Permintaan anonim tidak boleh mengubah transaksi atau ketersediaan barang.
    def test_anonymous_writes_do_not_modify_transactions(self):
        loan = self.loan()
        response = self.client.patch(self.url("detail", loan), {"notes": "Tidak boleh tersimpan"}, format="json")
        self.assertEqual(response.status_code, 403)

        for action in ("cancel", "approve", "reject", "mark-borrowed", "request-return", "complete"):
            with self.subTest(action=action):
                response = self.client.post(self.url(action, loan), {}, format="json")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response["Content-Type"], "application/json")

        loan.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(loan.status, LoanRequest.Status.PENDING)
        self.assertEqual(loan.notes, "")
        self.assertIsNone(loan.return_requested_at)
        self.assertTrue(self.item.is_available)

    # Timestamp pengembalian hanya diubah melalui endpoint pengajuan pengembalian.
    def test_return_timestamp_cannot_be_forged_through_input(self):
        self.login_as(self.borrower)
        forged_timestamp = timezone.now().isoformat()
        response = self.client.post(self.url(), self.data(return_requested_at=forged_timestamp), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        loan = LoanRequest.objects.get(pk=response.data["id"])
        self.assertIsNone(loan.return_requested_at)

        response = self.client.patch(
            self.url("detail", loan), {"return_requested_at": forged_timestamp}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)

        loan.refresh_from_db()
        self.assertIsNone(loan.return_requested_at)

    # ID barang yang tidak valid tidak membuat transaksi.
    def test_invalid_item_ids_are_rejected_without_creating_a_loan(self):
        self.login_as(self.borrower)

        for item_id in (999999999, "invalid-id", None):
            with self.subTest(item_id=item_id):
                response = self.client.post(self.url(), self.data(item=item_id), format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("item", response.data)

        self.assertFalse(LoanRequest.objects.exists())

    # PATCH dan POST aksi memerlukan CSRF yang valid.
    def test_session_csrf_required_for_patch_and_action_posts(self):
        loan = self.loan()
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.borrower)

        response = client.patch(self.url("detail", loan), {"notes": "Belum boleh berubah"}, format="json")
        self.assertEqual(response.status_code, 403)

        for action in ("cancel", "approve", "reject", "mark-borrowed", "request-return", "complete"):
            with self.subTest(action=action):
                self.assertEqual(client.post(self.url(action, loan), {}, format="json").status_code, 403)

        loan.refresh_from_db()
        self.assertEqual(loan.notes, "")
        self.assertEqual(loan.status, LoanRequest.Status.PENDING)

        client.get(reverse("loans:list"))
        token = client.cookies["csrftoken"].value
        response = client.patch(
            self.url("detail", loan), {"notes": "Catatan dengan CSRF valid"}, format="json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, 200, response.data)

        loan.refresh_from_db()
        self.assertEqual(loan.notes, "Catatan dengan CSRF valid")

        response = client.post(self.url("cancel", loan), {}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.data)

        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanRequest.Status.CANCELLED)
