from django.urls import path

from items import api_views

# Namespace unik per modul agar tidak bentrok dengan API modul lain.
app_name = "items_api"

urlpatterns = [
    path("", api_views.item_list, name="item-list"),
    path("mine/", api_views.item_mine, name="item-mine"),
    path("<int:item_id>/", api_views.item_detail, name="item-detail"),
]
