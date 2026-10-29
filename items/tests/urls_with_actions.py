"""URLconf test: proyek dengan URL aksi tersedia (view tiruan), untuk menguji tombol di detail barang."""
from django.urls import include, path
from django.views.generic import View

from items.tests.urls_without_actions import base_patterns, read_only_item_patterns

# View tiruan: test hanya memeriksa link yang dirender, bukan halaman tujuannya.
stub = View.as_view()

urlpatterns = base_patterns + [
    path("katalog/", include((read_only_item_patterns + [
        path("<int:pk>/edit/", stub, name="edit"),
        path("<int:pk>/hapus/", stub, name="delete"),
    ], "items"))),
    path("loans/", include(([
        path("ajukan/<int:item_id>/", stub, name="create"),
    ], "loans"))),
    path("review/", include(([
        path("reports/new/item/<int:item_id>/", stub, name="report_item_create"),
    ], "review"))),
]
