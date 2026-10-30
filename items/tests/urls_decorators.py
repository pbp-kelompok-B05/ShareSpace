"""URLconf test: view tiruan berdecorator item_owner_required, untuk menguji halaman 403 lewat client."""
from django.http import HttpResponse
from django.urls import include, path

from items.decorators import item_owner_required
from items.tests.urls_without_actions import base_patterns, read_only_item_patterns


@item_owner_required
def stub_edit(request, item):
    return HttpResponse("ok")


urlpatterns = base_patterns + [
    path("katalog/", include((read_only_item_patterns + [
        path("<int:pk>/edit/", stub_edit, name="edit"),
    ], "items"))),
]
