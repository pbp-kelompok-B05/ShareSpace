import datetime
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from django.utils.timesince import timesince
from items.decorators import rate_limit
from items.models import Item
from loans.models import LoanRequest
from review.moderation import staff_required
from review.models import Report, Review
from review.reputation import get_reputation

from authentication.backends import GoogleAuthBackend, SSOUIAuthBackend
from authentication.forms import LoginHelpRequestForm, UserProfileForm
from authentication.models import LoginHelpRequest, UserProfile


def format_relative_time_id(dt):
    """
    Memformat waktu relatif dalam bahasa Indonesia yang alami dan rapi.
    Contoh: '1 bulan yang lalu', '2 minggu yang lalu', '3 hari yang lalu', 'Baru saja'.
    """
    if not dt:
        return ""
    from django.utils import timezone
    now = timezone.now()
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Baru saja"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} menit yang lalu"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} jam yang lalu"
    days = diff.days
    if days == 1:
        return "Kemarin"
    if days < 7:
        return f"{days} hari yang lalu"
    if days < 30:
        weeks = days // 7
        return f"{weeks} minggu yang lalu"
    if days < 365:
        months = days // 30
        return f"{months} bulan yang lalu"
    years = days // 365
    return f"{years} tahun yang lalu"


class BaseProfileReputationProvider:
    """Kelas dasar abstrak penyedia reputasi profil pengguna."""

    def get_reputation_context(self, user):
        """Mengumpulkan context reputasi pengguna untuk profil."""
        raise NotImplementedError("Subclass harus mengimplementasikan get_reputation_context.")


class ReviewModuleReputationProvider(BaseProfileReputationProvider):
    """
    Penyedia reputasi profil yang mengintegrasikan modul resmi review.reputation milik Max.
    Menerapkan konsep Inheritance, Polymorphism, dan SOLID.
    """

    def get_reputation_context(self, user):
        reputation = get_reputation(user)

        reviews_qs = (
            Review.objects.visible()
            .filter(reviewee=user)
            .select_related("reviewer", "reviewer__userprofile", "loan", "loan__item")
            .order_by("-created_at")
        )
        reviews = list(reviews_qs[:5])

        for r in reviews:
            full_name = (
                r.reviewer.userprofile.full_name
                if hasattr(r.reviewer, "userprofile") and r.reviewer.userprofile.full_name
                else r.reviewer.username
            )
            r.reviewer_display_name = full_name
            r.reviewer_initial = full_name[0].upper() if full_name else "U"
            r.relative_time = format_relative_time_id(r.created_at)

        all_user_items_qs = Item.objects.filter(owner=user).order_by("-created_at")
        owned_items_total = all_user_items_qs.count()
        user_items = list(all_user_items_qs[:6])
        borrowed_loans_count = LoanRequest.objects.filter(borrower=user).count()

        trust_desc = {
            "new": "Belum cukup riwayat transaksi untuk menghitung Trust Score.",
            "excellent": "Pengguna memiliki reputasi luar biasa dan rekam jejak yang sangat terpercaya.",
            "trusted": "Pengguna terpercaya dengan riwayat transaksi yang konsisten dan baik.",
            "fair": "Pengguna aktif yang sedang membangun reputasi positif di komunitas.",
            "low": "Pengguna memiliki catatan transaksi atau ulasan yang perlu diperhatikan.",
        }.get(reputation.level.key, "Status reputasi pengguna di komunitas.")

        return {
            "reputation": reputation,
            "reviews": reviews,
            "reviews_count": reputation.review_count,
            "average_rating": reputation.average_rating,
            "completed_loans_count": reputation.completed_count,
            "borrowed_loans_count": borrowed_loans_count,
            "user_items": user_items,
            "owned_items_count": owned_items_total,
            "trust_score": reputation.score,
            "trust_level": reputation.level.label,
            "trust_description": trust_desc,
        }


reputation_service = ReviewModuleReputationProvider()


# Create your views here.
def register(request):
    if request.user.is_authenticated:
        return redirect("landing_page")

    form = UserCreationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        UserProfile.objects.create(user=user)
        messages.success(request, "Akun berhasil dibuat. Silakan login.")
        return redirect("authentication:login")

    context = {
        "form": form,
        "google_client_id": getattr(settings, "GOOGLE_CLIENT_ID", ""),
    }
    return render(request, "register.html", context)


def login_user(request):
    if request.user.is_authenticated:
        return redirect("landing_page")

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        response = redirect("landing_page")
        response.set_cookie("last_login", str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        return response

    context = {
        "form": form,
        "google_client_id": getattr(settings, "GOOGLE_CLIENT_ID", ""),
    }
    return render(request, "login.html", context)


def logout_user(request):
    logout(request)
    response = redirect("landing_page")
    response.delete_cookie("last_login")
    return response


def build_profile_context(request, profile):
    last_login = request.COOKIES.get("last_login", "Belum ada sesi login / Cookie tidak ditemukan")
    reputation_ctx = reputation_service.get_reputation_context(profile.user)

    return {
        "profile": profile,
        "last_login": last_login,
        **reputation_ctx,
    }


@login_required
def show_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    context = build_profile_context(request, profile)

    if request.headers.get("HX-Request"):
        return render(request, "profile_content.html", context)

    return render(request, "profile.html", context)


@login_required
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = UserProfileForm(request.POST or None, instance=profile)

    if request.method == "POST":
        if form.is_valid():
            form.save()

            # Respons HTMX tidak me-reload halaman, jadi toast dikirim lewat header HX-Trigger
            if request.headers.get("HX-Request"):
                context = build_profile_context(request, profile)
                response = render(request, "profile_content.html", context)
                response["HX-Trigger"] = json.dumps(
                    {"showToast": {"message": "Profil berhasil diperbarui!", "level": "success"}}
                )
                response["HX-Push-Url"] = reverse("authentication:profile")
                return response

            messages.success(request, "Profil berhasil diperbarui!")
            return redirect("authentication:profile")
        elif not request.headers.get("HX-Request"):
            messages.error(request, "Terdapat kesalahan pengisian form. Silakan periksa kembali.")

    context = {
        "profile": profile,
        "form": form,
    }

    template = "edit_profile_content.html" if request.headers.get("HX-Request") else "edit_profile.html"
    return render(request, template, context)


@login_required
@require_http_methods(["GET", "POST"])
def deactivate_account(request):
    if request.method == "POST":
        user = request.user
        user.is_active = False
        user.save()
        logout(request)
        messages.success(request, "Akun Anda telah berhasil dinonaktifkan.")
        response = redirect("landing_page")
        response.delete_cookie("last_login")
        return response

    return render(request, "deactivate_account.html")


class AdminModerationPermission:
    """Validator hierarki perizinan aksi moderasi akun oleh staf dan superuser (OOP SOLID)."""

    @classmethod
    def can_moderate(cls, actor, target_user):
        """
        Memeriksa apakah actor memiliki izin memoderasi target_user.
        Aturan:
        1. Aktor harus berupa staf yang terautentikasi.
        2. Pengguna tidak diizinkan memoderasi akun miliknya sendiri.
        3. Staf biasa tidak boleh memoderasi akun superuser maupun sesama akun staf.
        4. Superuser tidak boleh memoderasi akun superuser lainnya melalui panel ini.
        """
        if not actor or not actor.is_authenticated or not actor.is_staff:
            return False, "Anda tidak memiliki izin staf."
        if target_user.pk == actor.pk:
            return False, "Anda tidak dapat memoderasi akun Anda sendiri."
        if target_user.is_superuser or (target_user.is_staff and not actor.is_superuser):
            return False, "Kamu tidak punya izin memoderasi akun admin."
        return True, ""


class UserDeletionValidator:
    """Validator untuk memeriksa kelayakan penghapusan akun pengguna (OOP SOLID)."""

    @staticmethod
    def get_blocking_reasons(user):
        """Mengembalikan list alasan mengapa akun pengguna belum dapat dihapus."""
        reasons = []

        # 1. Transaksi peminjaman aktif (sebagai peminjam atau sebagai pemilik barang)
        active_statuses = [
            LoanRequest.Status.PENDING,
            LoanRequest.Status.APPROVED,
            LoanRequest.Status.BORROWED,
        ]
        has_borrowed_loans = LoanRequest.objects.filter(borrower=user, status__in=active_statuses).exists()
        has_lent_loans = LoanRequest.objects.filter(item__owner=user, status__in=active_statuses).exists()
        if has_borrowed_loans or has_lent_loans:
            reasons.append("Pengguna masih memiliki transaksi peminjaman aktif.")

        # 2. Barang aktif (belum di-soft delete)
        active_items = Item.objects.filter(owner=user, is_deleted=False)
        if active_items.exists():
            reasons.append("Pengguna masih memiliki barang yang aktif di katalog.")

        # 3. Laporan aktif (sebagai pelapor, terlapor langsung, atau pihak transaksi yang dilaporkan)
        has_filed_reports = Report.objects.filter(reporter=user, status__in=Report.ACTIVE_STATUSES).exists()
        has_targeted_reports = Report.objects.filter(target_user=user, status__in=Report.ACTIVE_STATUSES).exists()
        has_loan_reports = (
            Report.objects.filter(target_loan__borrower=user, status__in=Report.ACTIVE_STATUSES).exists()
            or Report.objects.filter(target_loan__item__owner=user, status__in=Report.ACTIVE_STATUSES).exists()
        )
        if has_filed_reports or has_targeted_reports or has_loan_reports:
            reasons.append("Pengguna masih terlibat dalam laporan yang sedang diproses.")

        return reasons


@login_required
def public_profile(request, username):
    if request.user.is_staff:
        target_user = get_object_or_404(User, username=username)
    else:
        target_user = get_object_or_404(User, username=username, is_active=True)

    if target_user.pk == request.user.pk:
        return redirect("authentication:profile")

    # Profil publik hanya menampilkan identitas, nomor telepon dan alamat tidak ikut dikirim ke template
    profile = UserProfile.objects.filter(user=target_user).first()
    reputation_ctx = reputation_service.get_reputation_context(target_user)

    can_moderate, _ = AdminModerationPermission.can_moderate(request.user, target_user)
    deletion_reasons = []
    if can_moderate:
        deletion_reasons = UserDeletionValidator.get_blocking_reasons(target_user)

    context = {
        "target_user": target_user,
        "profile": profile,
        "can_moderate": can_moderate,
        "can_be_deleted": can_moderate and len(deletion_reasons) == 0,
        "deletion_reasons": deletion_reasons,
        **reputation_ctx,
    }
    return render(request, "public_profile.html", context)


@require_http_methods(["POST"])
def google_login(request):
    """
    Endpoint autentikasi Google Identity Services (GSI).
    Menerima ID token credential via POST form atau JSON payload dengan proteksi CSRF standar.
    """
    if request.user.is_authenticated:
        if request.content_type == "application/json":
            return JsonResponse({"status": "success", "redirect_url": reverse("landing_page")})
        return redirect("landing_page")

    is_json = request.content_type == "application/json"
    credential = request.POST.get("credential")
    if not credential and is_json:
        try:
            body = json.loads(request.body)
            credential = body.get("credential")
        except Exception as e:
            credential = None

    if not credential:
        if is_json:
            return JsonResponse({"status": "error", "message": "Kredensial Google tidak ditemukan."}, status=400)
        messages.error(request, "Kredensial Google tidak ditemukan.")
        return redirect("authentication:login")

    user = authenticate(request, google_credential=credential)

    if not user:
        if is_json:
            return JsonResponse({"status": "error", "message": "Autentikasi Google gagal atau token tidak valid."}, status=400)
        messages.error(request, "Autentikasi Google gagal atau token tidak valid.")
        return redirect("authentication:login")

    login(request, user)
    messages.success(request, f"Selamat datang, {user.username}! Berhasil masuk via Google.")

    if is_json:
        response = JsonResponse({"status": "success", "redirect_url": reverse("landing_page")})
    else:
        response = redirect("landing_page")

    response.set_cookie(
        "last_login",
        str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    return response


@require_http_methods(["GET"])
def sso_ui_login(request):
    """
    Mengarahkan pengguna ke halaman login CAS SSO UI.
    """
    if request.user.is_authenticated:
        return redirect("landing_page")

    service_url = request.build_absolute_uri(reverse("authentication:sso_ui_callback"))
    return redirect(SSOUIAuthBackend.get_login_url(service_url))


@require_http_methods(["GET"])
def sso_ui_callback(request):
    """
    Callback handler dari CAS SSO UI setelah pengguna berhasil login.
    """
    if request.user.is_authenticated:
        return redirect("landing_page")

    ticket = request.GET.get("ticket")
    if not ticket:
        messages.error(request, "Tiket otorisasi SSO UI tidak ditemukan.")
        return redirect("authentication:login")

    service_url = request.build_absolute_uri(reverse("authentication:sso_ui_callback"))
    user = authenticate(request, sso_ticket=ticket, service_url=service_url)

    if not user:
        messages.error(request, "Autentikasi SSO UI gagal. Silakan coba kembali.")
        return redirect("authentication:login")

    login(request, user)
    messages.success(request, f"Selamat datang civitas UI, {user.username}! Berhasil masuk via SSO UI.")
    response = redirect("landing_page")
    response.set_cookie(
        "last_login",
        str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    return response


@require_GET
@login_required
def profile_reputation_api(request, username=None):
    """
    Endpoint AJAX JSON yang mengembalikan metrik reputasi, Trust Score,
    dan daftar ulasan komunitas untuk profil pengguna.
    """
    if username:
        target_user = get_object_or_404(User, username=username, is_active=True)
    else:
        target_user = request.user

    reputation_ctx = reputation_service.get_reputation_context(target_user)

    reviews_data = [
        {
            "id": str(r.pk),
            "reviewer_username": r.reviewer.username,
            "reviewer_name": r.reviewer_display_name,
            "reviewer_initial": r.reviewer_initial,
            "reviewer_role": r.reviewer_role,
            "reviewer_role_display": "Peminjam" if r.reviewer_role == "borrower" else "Pemilik Barang",
            "item_name": r.loan.item.name if r.loan and r.loan.item else "",
            "rating": r.rating,
            "comment": r.comment,
            "relative_time": r.relative_time,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for r in reputation_ctx["reviews"]
    ]

    items_data = [
        {
            "id": item.pk,
            "name": item.name,
            "image_url": item.image_url or "",
            "is_available": item.is_available,
            "detail_url": reverse("items:detail", args=[item.pk]),
        }
        for item in reputation_ctx["user_items"]
    ]

    return JsonResponse(
        {
            "status": "success",
            "username": target_user.username,
            "trust_score": reputation_ctx["trust_score"],
            "trust_level": reputation_ctx["trust_level"],
            "trust_description": reputation_ctx["trust_description"],
            "average_rating": (
                round(reputation_ctx["average_rating"], 1)
                if reputation_ctx["average_rating"] is not None
                else None
            ),
            "reviews_count": reputation_ctx["reviews_count"],
            "completed_loans_count": reputation_ctx["completed_loans_count"],
            "borrowed_loans_count": reputation_ctx["borrowed_loans_count"],
            "owned_items_count": reputation_ctx["owned_items_count"],
            "reviews": reviews_data,
            "user_items": items_data,
        }
    )

@require_http_methods(["GET", "POST"])
@rate_limit(scope="login_help", limit=5, period=60)
def login_help_request(request):
    """
    View publik untuk mengajukan permohonan bantuan kendala login atau lupa password.
    Hanya dapat diakses oleh tamu yang belum login (unauthenticated).
    """
    if request.user.is_authenticated:
        return redirect("landing_page")

    if request.method == "POST":
        form = LoginHelpRequestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Permohonan bantuan Anda telah diterima. Jika akun terdaftar, admin akan menghubungi email kontakmu.",
            )
            return redirect("authentication:login")
    else:
        form = LoginHelpRequestForm()

    context = {
        "form": form,
    }
    return render(request, "login_help_form.html", context)


@staff_required
@require_http_methods(["POST"])
def admin_toggle_verify(request, username):
    """
    Mengubah status verifikasi profil pengguna (is_verified).
    Hanya dapat diakses oleh staff/admin dengan hierarki moderasi yang valid.
    """
    target_user = get_object_or_404(User, username=username)

    allowed, error_msg = AdminModerationPermission.can_moderate(request.user, target_user)
    if not allowed:
        messages.error(request, error_msg)
        return redirect("authentication:public_profile", username=username)

    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    profile.is_verified = not profile.is_verified
    profile.save()

    status_str = "terverifikasi" if profile.is_verified else "tidak terverifikasi"
    messages.success(
        request,
        f"Status verifikasi akun {target_user.username} berhasil diubah menjadi {status_str}.",
    )
    return redirect("authentication:public_profile", username=username)


@staff_required
@require_http_methods(["POST"])
def admin_toggle_active(request, username):
    """
    Mengubah status aktif akun pengguna (is_active).
    Admin tidak diizinkan menonaktifkan akun admin lain tanpa hak superuser atau akunnya sendiri.
    """
    target_user = get_object_or_404(User, username=username)

    allowed, error_msg = AdminModerationPermission.can_moderate(request.user, target_user)
    if not allowed:
        messages.error(request, error_msg)
        return redirect("authentication:public_profile", username=username)

    target_user.is_active = not target_user.is_active
    target_user.save()

    status_str = "aktif" if target_user.is_active else "nonaktif"
    messages.success(
        request,
        f"Status akun {target_user.username} berhasil diubah menjadi {status_str}.",
    )
    return redirect("authentication:public_profile", username=username)


@staff_required
@require_http_methods(["POST"])
def admin_delete_user(request, username):
    """
    Menghapus akun pengguna secara aman setelah memeriksa ketiadaan relasi data aktif.
    Admin tidak diizinkan menghapus akun admin lain tanpa hak superuser atau akunnya sendiri.
    """
    target_user = get_object_or_404(User, username=username)

    allowed, error_msg = AdminModerationPermission.can_moderate(request.user, target_user)
    if not allowed:
        messages.error(request, error_msg)
        return redirect("authentication:public_profile", username=username)

    reasons = UserDeletionValidator.get_blocking_reasons(target_user)
    if reasons:
        error_msg = "Akun tidak dapat dihapus: " + " ".join(reasons)
        messages.error(request, error_msg)
        return redirect("authentication:public_profile", username=username)

    try:
        deleted_username = target_user.username
        target_user.delete()
        messages.success(request, f"Akun pengguna {deleted_username} berhasil dihapus.")
        return redirect("landing_page")
    except Exception as e:
        messages.error(
            request,
            "Gagal menghapus pengguna karena masih ada relasi data yang dilindungi di sistem.",
        )
        return redirect("authentication:public_profile", username=username)

