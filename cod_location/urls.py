
from django.urls import path
from . import views

app_name = "cod_location"

urlpatterns = [
    # Halaman peta COD
    path(
        "",
        views.cod_map_page,
        name="map",
    ),

    # CRUD Lokasi COD
    path(
        "locations/",
        views.location_list,
        name="location_list",
    ),
    path(
        "locations/create/",
        views.location_create,
        name="location_create",
    ),
    path(
        "locations/<uuid:pk>/",
        views.location_detail,
        name="location_detail",
    ),
    path(
        "locations/<uuid:pk>/update/",
        views.location_update,
        name="location_update",
    ),
    path(
        "locations/<uuid:pk>/delete/",
        views.location_delete,
        name="location_delete",
    ),

    # CRUD Jadwal COD
    path(
        "loans/<uuid:loan_id>/schedules/",
        views.schedule_list,
        name="schedule_list",
    ),
    path(
        "loans/<uuid:loan_id>/schedules/create/",
        views.schedule_create,
        name="schedule_create",
    ),
    path(
        "schedules/<uuid:pk>/",
        views.schedule_detail,
        name="schedule_detail",
    ),
    path(
        "schedules/<uuid:pk>/update/",
        views.schedule_update,
        name="schedule_update",
    ),
    path(
        "schedules/<uuid:pk>/delete/",
        views.schedule_delete,
        name="schedule_delete",
    ),
    path(
        "overpass/", 
        views.overpass_search, 
        name="overpass_search"
    ),
    path(
        "loans/<uuid:loan_id>/manage/",
        views.schedule_manage_page,
        name="schedule_manage",
    ),
]
