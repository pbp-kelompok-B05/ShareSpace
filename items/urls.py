from django.urls import path

from items import views

app_name = "items"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("json/", views.catalog_json, name="catalog_json"),
    path("tambah/", views.item_create, name="create"),
    path("saya/", views.my_items, name="my_items"),
    path("<int:pk>/", views.item_detail, name="detail"),
    path("<int:pk>/json/", views.item_detail_json, name="detail_json"),
    path("<int:pk>/edit/", views.item_edit, name="edit"),
    path("<int:pk>/hapus/", views.item_delete, name="delete"),
]
