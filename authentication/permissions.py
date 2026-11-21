from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsProfileOwnerOrReadOnly(BasePermission):
    message = "Hanya pemilik profil yang dapat mengubah data ini."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and obj.user_id == request.user.pk
        )


class IsUnauthenticatedOnly(BasePermission):
    message = "Permohonan bantuan login hanya dapat dikirim oleh pengguna yang belum login."

    def has_permission(self, request, view):
        return not (request.user and request.user.is_authenticated)
