import json
from urllib.parse import urlsplit

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from items.decorators import (
    htmx_login_required, hx_redirect, is_htmx, item_owner_required, rate_limit, toast_response,
)
from items.forms import BulkItemActionForm, CatalogFilterForm, ItemForm, MyItemsFilterForm
from items.models import Item
from items.serializers import serialize_item

CATALOG_PAGE_SIZE = 12
MY_ITEMS_PAGE_SIZE = 20  # daftar baris lebih padat daripada grid card katalog
ITEM_CREATE_RATE_LIMIT = 10  # POST per jam per user
ITEM_UPDATE_RATE_LIMIT = 30  # POST per jam per user
ITEM_BULK_RATE_LIMIT = 60  # POST per jam per user; aksi cepat per baris ikut dihitung


def _visible_items():
    """Barang yang boleh dilihat publik, beserta pemiliknya dalam satu query."""
    return Item.objects.visible().select_related("owner")


def _catalog_page(request):
    """Filter + pagination bersama untuk katalog HTML dan JSON."""
    filter_form = CatalogFilterForm(request.GET)
    queryset = filter_form.apply(_visible_items())
    page_obj = Paginator(queryset, CATALOG_PAGE_SIZE).get_page(request.GET.get("page"))
    return filter_form, page_obj


def _is_htmx_partial(request):
    """Request HTMX biasa mendapat partial; history restore butuh halaman penuh."""
    return (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-History-Restore-Request") != "true"
    )


def _htmx_from_path(request, path):
    """Request HTMX dikirim dari halaman `path`; tanpa header HX-Current-URL dianggap ya."""
    current_url = request.headers.get("HX-Current-URL")
    return current_url is None or urlsplit(current_url).path == path


@require_GET
def catalog(request):
    filter_form, page_obj = _catalog_page(request)
    context = {"filter_form": filter_form, "page_obj": page_obj}
    template = "items/partials/item_list.html" if _is_htmx_partial(request) else "items/catalog.html"
    response = render(request, template, context)
    # Halaman penuh dan partial memakai URL sama; cache browser harus membedakannya.
    patch_vary_headers(response, ["HX-Request"])
    return response


def _my_items_context(request, data):
    """Daftar "Barang saya" (tab aktif/terhapus + filter + halaman) dari query string atau POST."""
    filter_form = MyItemsFilterForm(data)
    if filter_form.show_deleted:
        own_items = Item.all_objects.filter(owner=request.user, is_deleted=True)
    else:
        # Termasuk barang yang sedang dipinjam; soft delete disaring manager default.
        own_items = Item.objects.filter(owner=request.user)
    page_obj = Paginator(filter_form.apply(own_items), MY_ITEMS_PAGE_SIZE).get_page(data.get("page"))
    return {"filter_form": filter_form, "page_obj": page_obj, "show_deleted": filter_form.show_deleted}


def _my_items_stats(user):
    """Ringkasan barang aktif milik user dalam satu query; sengaja tidak mengikuti filter."""
    return Item.objects.filter(owner=user).aggregate(
        total=Count("pk"),
        available=Count("pk", filter=Q(is_available=True)),
        borrowed=Count("pk", filter=Q(is_available=False)),
    )


@require_GET
@htmx_login_required
def my_items(request):
    context = _my_items_context(request, request.GET)
    if _is_htmx_partial(request):
        template = "items/partials/my_item_list.html"
    else:
        template = "items/my_items.html"
        context["stats"] = _my_items_stats(request.user)
    response = render(request, template, context)
    patch_vary_headers(response, ["HX-Request"])
    return response


@require_POST
@htmx_login_required
@rate_limit("item_bulk", limit=ITEM_BULK_RATE_LIMIT, period=60 * 60)
def item_bulk_action(request):
    """Hapus/pulihkan beberapa barang milik sendiri sekaligus (juga dipakai aksi cepat per baris)."""
    form = BulkItemActionForm(request.user, request.POST)
    my_items_url = reverse("items:my_items")
    if not form.is_valid():
        message = next(iter(form.errors.values()))[0]
        if is_htmx(request):
            # 4xx tidak di-swap HTMX; my-items.js mengembalikan baris yang sudah disembunyikan (optimistic UI).
            return toast_response(message, 400)
        messages.error(request, message)
        return redirect(my_items_url)

    changed, skipped = form.save()
    message = form.result_message(changed, skipped)
    level = "success" if changed else "warning"
    if not is_htmx(request):
        messages.add_message(request, messages.SUCCESS if changed else messages.WARNING, message)
        if form.cleaned_data["action"] == "restore":
            my_items_url += "?status=deleted"
        return redirect(my_items_url)

    # HTMX: daftar dirender ulang dengan filter dan halaman yang ikut dikirim (hx-include),
    # ringkasan diperbarui lewat hx-swap-oob.
    context = _my_items_context(request, request.POST)
    context["stats"] = _my_items_stats(request.user)
    response = render(request, "items/partials/my_items_bulk_result.html", context)
    response["HX-Trigger"] = json.dumps({"showToast": {"message": message, "level": level}})
    return response


@require_GET
def catalog_json(request):
    _, page_obj = _catalog_page(request)
    paginator = page_obj.paginator
    return JsonResponse({
        "count": paginator.count,
        "num_pages": paginator.num_pages,
        "page": page_obj.number,
        "page_size": paginator.per_page,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
        "results": [serialize_item(item, request) for item in page_obj.object_list],
    })


@require_GET
def item_detail(request, pk):
    # Soft delete disaring manager default; visible() menyaring pemilik nonaktif. Keduanya 404.
    item = get_object_or_404(_visible_items(), pk=pk)
    can_manage = item.can_be_managed_by(request.user)
    context = {
        "item": item,
        "can_manage": can_manage,
        # Dialog edit/hapus hanya dipasang jika aksinya memang boleh dilakukan.
        "show_item_dialog": can_manage and item.is_available,
    }
    return render(request, "items/detail.html", context)


@require_GET
def item_detail_json(request, pk):
    try:
        item = _visible_items().get(pk=pk)
    except Item.DoesNotExist:
        # Klien API (Flutter) selalu menerima JSON, bukan halaman 404 HTML.
        return JsonResponse({"detail": "Barang tidak ditemukan."}, status=404)
    return JsonResponse(serialize_item(item, request))


@require_http_methods(["GET", "POST"])
@htmx_login_required
@rate_limit("item_create", limit=ITEM_CREATE_RATE_LIMIT, period=60 * 60)
def item_create(request):
    # request.POST kosong tetap harus jadi form terikat agar error "wajib diisi" muncul.
    form = ItemForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        item.save()
        messages.success(request, f"{item.name} berhasil ditambahkan ke katalog.")
        detail_url = reverse("items:detail", args=[item.pk])
        # HTMX: pindah ke detail lewat HX-Redirect; pesan sukses tampil sebagai toast di sana.
        return hx_redirect(detail_url) if is_htmx(request) else redirect(detail_url)

    context = {
        "form": form,
        "page_title": "Pinjamkan Barang",
        "page_subtitle": "Daftarkan barang yang bisa dipinjam tetangga di sekitarmu.",
        "form_action": reverse("items:create"),
        "submit_label": "Simpan Barang",
        "cancel_url": reverse("items:catalog"),
    }
    # Error validasi via HTMX: hanya form yang diganti (hx-swap outerHTML).
    template = "items/partials/item_form.html" if is_htmx(request) else "items/item_form.html"
    return render(request, template, context)


@require_http_methods(["GET", "POST"])
@item_owner_required
@rate_limit("item_update", limit=ITEM_UPDATE_RATE_LIMIT, period=60 * 60)
def item_edit(request, item):
    detail_url = reverse("items:detail", args=[item.pk])
    form = ItemForm(request.POST if request.method == "POST" else None, instance=item)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        message = f"Perubahan pada {item.name} berhasil disimpan."
        if not is_htmx(request):
            messages.success(request, message)
            return redirect(detail_url)
        if not _htmx_from_path(request, detail_url):
            # Form HTMX di halaman lain (mis. halaman edit penuh) tidak punya #item-detail: pindah ke detail.
            messages.success(request, message)
            return hx_redirect(detail_url)
        # HTMX (dari dialog di detail): ganti isi detail di tempat, tutup dialog, tampilkan toast.
        context = {"item": item, "can_manage": item.can_be_managed_by(request.user)}
        response = render(request, "items/partials/item_detail_updated.html", context)
        response["HX-Retarget"] = "#item-detail"
        response["HX-Reswap"] = "outerHTML"
        response["HX-Trigger"] = json.dumps({
            "showToast": {"message": message, "level": "success"},
            "closeItemDialog": True,
        })
        return response

    context = {
        "form": form,
        "item": item,
        "page_title": "Edit Barang",
        "page_subtitle": "Perbarui informasi barang. Status ketersediaan diatur otomatis oleh sistem peminjaman.",
        "form_action": reverse("items:edit", args=[item.pk]),
        "submit_label": "Simpan Perubahan",
        "cancel_url": detail_url,
    }
    if not is_htmx(request):
        template = "items/item_form.html"
    elif request.method == "GET":
        template = "items/partials/item_edit_dialog.html"
    else:
        template = "items/partials/item_form.html"
    return render(request, template, context)


@require_http_methods(["GET", "POST"])
@item_owner_required
def item_delete(request, item):
    if request.method == "POST":
        # Soft delete: baris tetap ada untuk riwayat peminjaman (FK loans PROTECT).
        # Tanpa force: barang dipinjam sudah ditolak decorator dengan 403.
        item.soft_delete()
        messages.success(request, f"{item.name} berhasil dihapus dari katalog.")
        # Pemilik kembali ke "Barang saya" (barang bisa dipulihkan dari tab Terhapus);
        # admin yang menghapus barang orang lain kembali ke katalog.
        next_url = reverse("items:my_items" if item.owner_id == request.user.pk else "items:catalog")
        # Detail barang sudah 404, jadi HTMX juga pindah halaman; toast tampil dari messages.
        return hx_redirect(next_url) if is_htmx(request) else redirect(next_url)

    context = {
        "item": item,
        "form_action": reverse("items:delete", args=[item.pk]),
        "cancel_url": reverse("items:detail", args=[item.pk]),
    }
    template = "items/partials/item_delete_dialog.html" if is_htmx(request) else "items/item_confirm_delete.html"
    return render(request, template, context)
