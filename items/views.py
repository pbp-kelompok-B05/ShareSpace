from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET

from items.forms import CatalogFilterForm
from items.models import Item
from items.serializers import serialize_item

CATALOG_PAGE_SIZE = 12


def _catalog_page(request):
    """Filter + pagination bersama untuk katalog HTML dan JSON."""
    filter_form = CatalogFilterForm(request.GET)
    queryset = filter_form.apply(Item.objects.visible().select_related("owner"))
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
