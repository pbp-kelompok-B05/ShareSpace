"""URLconf test: proyek tanpa URL aksi (edit/hapus barang, ajukan pinjaman, laporkan barang).

Namespace items, loans, dan review dibangun ulang di sini agar hasil test tidak
bergantung pada app anggota lain yang sudah atau belum di-merge.
"""
from django.urls import include, path

from items.urls import urlpatterns as items_patterns
from ShareSpace.urls import urlpatterns as project_patterns

REPLACED_NAMESPACES = {"items", "loans", "review"}
READ_ONLY_ITEM_URLS = {"catalog", "catalog_json", "detail", "detail_json"}

base_patterns = [
    pattern for pattern in project_patterns
    if getattr(pattern, "namespace", None) not in REPLACED_NAMESPACES
]
read_only_item_patterns = [p for p in items_patterns if p.name in READ_ONLY_ITEM_URLS]

urlpatterns = base_patterns + [
    path("katalog/", include((read_only_item_patterns, "items"))),
]
