"""Helper HTMX bersama untuk view modul review."""
from django.shortcuts import render
from django.utils.cache import patch_vary_headers

# Respons halaman daftar berbeda menurut header ini, jadi cache harus membedakannya.
HTMX_VARY_HEADERS = ("HX-Request", "HX-History-Restore-Request")


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def wants_partial(request):
    """True jika HTMX meminta potongan halaman.

    Saat history cache meleset (tombol Back), htmx 2 tetap mengirim HX-Request tetapi
    juga HX-History-Restore-Request, lalu men-swap respons ke <body>. Permintaan itu
    harus mendapat halaman penuh agar navbar dan layout tidak hilang.
    """
    return is_htmx(request) and request.headers.get("HX-History-Restore-Request") != "true"


def render_list(request, full_template, partial_template, context):
    """Render halaman daftar penuh atau partial-nya, dengan header Vary yang benar."""
    template = partial_template if wants_partial(request) else full_template
    response = render(request, template, context)
    patch_vary_headers(response, HTMX_VARY_HEADERS)
    return response
