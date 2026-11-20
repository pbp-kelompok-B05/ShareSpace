"""API view Modul 2 (Django REST Framework), mengikuti pola Tutorial 07.

Alur request: URL -> SessionAuthentication -> permission -> method -> view -> serializer -> Response.
Autentikasi memakai session (cookie), jadi POST/PUT/PATCH/DELETE wajib menyertakan token CSRF.
"""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from items.decorators import BORROWED_MESSAGE
from items.forms import CatalogFilterForm
from items.models import Item
from items.permissions import IsAuthenticatedOrReadOnly, IsItemOwnerOrAdminOrReadOnly
from items.serializers import ItemSerializer

object_permission = IsItemOwnerOrAdminOrReadOnly()


def _visible_items():
    """Barang yang boleh dilihat publik, beserta pemiliknya dalam satu query."""
    return Item.objects.visible().select_related("owner")


def _filtered(request, queryset):
    """Filter dan urutan yang sama dengan katalog web: q, category, condition, available, sort."""
    return CatalogFilterForm(request.query_params).apply(queryset)


def _check_manageable(request, item):
    """Ubah/hapus hanya oleh pemilik atau admin, dan hanya selagi barang tidak dipinjam."""
    # Kepemilikan dicek dulu agar user lain tidak tahu status peminjaman barang orang lain.
    if not object_permission.has_object_permission(request, None, item):
        raise PermissionDenied(object_permission.message)
    if request.method not in ("GET", "HEAD", "OPTIONS") and not item.is_available:
        raise PermissionDenied(BORROWED_MESSAGE)


@api_view(["GET", "HEAD", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticatedOrReadOnly])
def item_list(request):
    if request.method in ("GET", "HEAD"):
        items = _filtered(request, _visible_items())
        return Response(ItemSerializer(items, many=True, context={"request": request}).data)

    serializer = ItemSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    # Pemilik selalu akun yang login; klien tidak boleh memilihnya.
    serializer.save(owner=request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "HEAD"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def item_mine(request):
    """Barang milik akun yang login (yang belum dihapus)."""
    items = _filtered(request, Item.objects.filter(owner=request.user).select_related("owner"))
    return Response(ItemSerializer(items, many=True, context={"request": request}).data)


@api_view(["GET", "HEAD", "PUT", "PATCH", "DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticatedOrReadOnly])
def item_detail(request, item_id):
    # Barang terhapus disaring manager default dan pemilik nonaktif oleh visible(); keduanya 404.
    item = get_object_or_404(_visible_items(), pk=item_id)
    _check_manageable(request, item)

    if request.method in ("GET", "HEAD"):
        return Response(ItemSerializer(item, context={"request": request}).data)

    if request.method == "DELETE":
        # Soft delete: baris tetap ada untuk riwayat peminjaman (FK loans PROTECT).
        item.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = ItemSerializer(
        item, data=request.data, partial=request.method == "PATCH",
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)
