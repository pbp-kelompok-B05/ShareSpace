from django.urls import path

from items import views

app_name = "items"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("json/", views.catalog_json, name="catalog_json"),
    path("<int:pk>/", views.item_detail, name="detail"),
    path("<int:pk>/json/", views.item_detail_json, name="detail_json"),
]
