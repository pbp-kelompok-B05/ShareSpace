"""Permission class API Modul 2: baca untuk semua pengunjung, tulis untuk pemilik atau admin."""
from rest_framework.permissions import SAFE_METHODS, BasePermission

# Pesan yang sama dengan view HTML agar web dan API konsisten.
from items.decorators import BORROWED_MESSAGE, FORBIDDEN_MESSAGE  # noqa: F401


class IsAuthenticatedOrReadOnly(BasePermission):
    """Level view: GET/HEAD/OPTIONS untuk semua; POST/PUT/PATCH/DELETE butuh login.

    Pengunjung anonim yang menulis mendapat 403 (SessionAuthentication tidak punya 401).
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(
            request.user and request.user.is_authenticated
        )


class IsItemOwnerOrAdminOrReadOnly(BasePermission):
    """Level objek: ubah/hapus hanya oleh pemilik atau admin (is_staff).

    DRF tidak memanggil ini otomatis pada function view; view memanggil
    has_object_permission() sendiri setelah objek ditemukan.
    """

    message = FORBIDDEN_MESSAGE

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or obj.can_be_managed_by(request.user)
