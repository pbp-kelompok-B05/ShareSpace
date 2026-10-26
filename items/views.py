from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET, require_http_methods

from items.decorators import htmx_login_required, hx_redirect, is_htmx, rate_limit
from items.forms import CatalogFilterForm, ItemForm
from items.models import Item
from items.serializers import serialize_item

CATALOG_PAGE_SIZE = 12
ITEM_CREATE_RATE_LIMIT = 10  # POST per jam per user


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


@require_GET
def catalog(request):
    filter_form, page_obj = _catalog_page(request)
    context = {"filter_form": filter_form, "page_obj": page_obj}
    template = "items/partials/item_list.html" if _is_htmx_partial(request) else "items/catalog.html"
    response = render(request, template, context)
    # Halaman penuh dan partial memakai URL sama; cache browser harus membedakannya.
    patch_vary_headers(response, ["HX-Request"])
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
    context = {"item": item, "can_manage": item.can_be_managed_by(request.user)}
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
