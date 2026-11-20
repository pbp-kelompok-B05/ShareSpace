
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsLocationCreatorOrStaff(BasePermission):
    """
    Semua pengguna yang sudah login boleh melihat lokasi.
    Hanya pembuat lokasi atau staff yang boleh mengubah dan menghapus.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        return (
            obj.created_by_id == request.user.id
            or request.user.is_staff
        )
