from django.urls import path

from items import views

app_name = "items"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("json/", views.catalog_json, name="catalog_json"),
]
