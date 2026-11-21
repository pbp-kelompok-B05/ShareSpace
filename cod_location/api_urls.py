
from django.urls import path
from . import api_views

app_name = "cod_location_api"

urlpatterns = [
    # COD Location
    path(
        "locations/",
        api_views.CODLocationListCreateAPIView.as_view(),
        name="location-list-create",
    ),
    path(
        "locations/<uuid:pk>/",
        api_views.CODLocationDetailAPIView.as_view(),
        name="location-detail",
    ),

    # Pickup Schedule
    path(
        "loans/<uuid:loan_id>/schedules/",
        api_views.LoanScheduleListCreateAPIView.as_view(),
        name="schedule-list-create",
    ),
    path(
        "schedules/<uuid:pk>/",
        api_views.PickupScheduleDetailAPIView.as_view(),
        name="schedule-detail",
    ),

    # Place Search
    path(
        "places/",
        api_views.PlaceListAPIView.as_view(),
        name="place-list",
    ),
]
