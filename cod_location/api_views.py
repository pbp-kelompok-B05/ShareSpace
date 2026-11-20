
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from math import atan2, cos, radians, sin, sqrt
from rest_framework.response import Response
from django.db.models.deletion import ProtectedError
from rest_framework import status

from loans.models import LoanRequest

from cod_location.models import CODLocation, PickupSchedule, Place
from cod_location.serializers import CODLocationSerializer, PickupScheduleSerializer, PlaceSerializer
from cod_location.permissions import IsLocationCreatorOrStaff
from cod_location.pagination import CODPlacesPagination


# ==================================================
# HELPER
# ==================================================

def get_accessible_loan(user, loan_id):
    """
    Mengambil pinjaman jika pengguna adalah borrower,
    pemilik barang, atau superuser.
    """

    queryset = LoanRequest.objects.select_related(
        "borrower",
        "item",
        "item__owner",
    )

    if not user.is_superuser:
        queryset = queryset.filter(
            Q(borrower=user) | Q(item__owner=user)
        )

    return get_object_or_404(queryset, pk=loan_id)


# ==================================================
# COD LOCATION
# ==================================================

class CODLocationListCreateAPIView(generics.ListCreateAPIView):
    queryset = CODLocation.objects.select_related("created_by").all()
    serializer_class = CODLocationSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)



class CODLocationDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CODLocation.objects.select_related("created_by").all()
    serializer_class = CODLocationSerializer
    permission_classes = [
        IsAuthenticated,
        IsLocationCreatorOrStaff,
    ]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {
                    "success": False,
                    "message": (
                        "Lokasi masih digunakan dalam jadwal COD."
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)



# ==================================================
# PICKUP SCHEDULE
# ==================================================

class LoanScheduleListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = PickupScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_loan(self):
        if not hasattr(self, "_loan"):
            self._loan = get_accessible_loan(
                self.request.user,
                self.kwargs["loan_id"],
            )

        return self._loan

    def get_queryset(self):
        return PickupSchedule.objects.filter(
            loan_request=self.get_loan()
        ).select_related(
            "cod_location",
            "created_by",
            "loan_request",
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["loan_request"] = self.get_loan()
        return context

    def perform_create(self, serializer):
        loan = self.get_loan()

        if loan.status not in ["pending", "approved", "borrowed"]:
            raise ValidationError(
                "Jadwal tidak dapat dibuat untuk status pinjaman ini."
            )

        serializer.save(
            loan_request=loan,
            created_by=self.request.user,
        )


class PickupScheduleDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PickupScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PickupSchedule.objects.select_related(
            "loan_request",
            "loan_request__borrower",
            "loan_request__item",
            "loan_request__item__owner",
            "cod_location",
            "created_by",
        )

        if not self.request.user.is_superuser:
            queryset = queryset.filter(
                Q(loan_request__borrower=self.request.user)
                | Q(loan_request__item__owner=self.request.user)
            )

        return queryset

    def perform_update(self, serializer):
        loan = serializer.instance.loan_request

        if loan.status not in ["pending", "approved", "borrowed"]:
            raise ValidationError(
                "Jadwal tidak dapat diubah untuk status pinjaman ini."
            )

        serializer.save()

    def perform_destroy(self, instance):
        loan = instance.loan_request

        if loan.status not in ["pending", "approved"]:
            raise ValidationError(
                "Jadwal hanya dapat dihapus saat pinjaman pending atau approved."
            )

        instance.delete()


# ==================================================
# PLACE / REKOMENDASI TEMPAT
# ==================================================


class PlaceListAPIView(generics.ListAPIView):
    serializer_class = PlaceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CODPlacesPagination

    def get_search_params(self):
        params = self.request.query_params

        raw_lat = params.get("latitude")
        raw_lon = params.get("longitude")
        raw_radius = params.get("radius")

        has_lat = raw_lat not in (None, "")
        has_lon = raw_lon not in (None, "")

        if has_lat != has_lon:
            raise ValidationError(
                "Latitude dan longitude harus diberikan bersama."
            )

        if not has_lat and raw_radius not in (None, ""):
            raise ValidationError(
                "Radius membutuhkan latitude dan longitude."
            )

        if not has_lat:
            return {
                "latitude": None,
                "longitude": None,
                "radius": None,
            }

        try:
            latitude = float(raw_lat)
            longitude = float(raw_lon)
            radius = float(raw_radius or 1000)
        except (TypeError, ValueError):
            raise ValidationError("Parameter koordinat atau radius tidak valid.")

        if not -90 <= latitude <= 90:
            raise ValidationError("Latitude harus antara -90 dan 90.")

        if not -180 <= longitude <= 180:
            raise ValidationError("Longitude harus antara -180 dan 180.")

        if not 1 <= radius <= 50000:
            raise ValidationError("Radius harus antara 1 dan 50000 meter.")

        return {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius,
        }

    def get_queryset(self):
        queryset = Place.objects.all()

        keyword = self.request.query_params.get(
            "keyword", ""
        ).strip()

        kind = self.request.query_params.get(
            "kind", ""
        ).strip()

        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(address__icontains=keyword)
            )

        if kind and kind.lower() != "all":
            queryset = queryset.filter(kind__iexact=kind)

        params = self.get_search_params()

        latitude = params["latitude"]
        longitude = params["longitude"]
        radius = params["radius"]

        if latitude is not None:
            # Penyaringan awal menggunakan bounding box
            lat_delta = radius / 111320

            cos_lat = abs(cos(radians(latitude)))

            lon_delta = (
                radius / (111320 * cos_lat)
                if cos_lat > 0.000001
                else 180
            )

            queryset = queryset.filter(
                latitude__gte=max(-90, latitude - lat_delta),
                latitude__lte=min(90, latitude + lat_delta),
            )

            if lon_delta < 180:
                min_lon = longitude - lon_delta
                max_lon = longitude + lon_delta

                if min_lon < -180:
                    queryset = queryset.filter(
                        Q(longitude__gte=min_lon + 360)
                        | Q(longitude__lte=max_lon)
                    )
                elif max_lon > 180:
                    queryset = queryset.filter(
                        Q(longitude__gte=min_lon)
                        | Q(longitude__lte=max_lon - 360)
                    )
                else:
                    queryset = queryset.filter(
                        longitude__gte=min_lon,
                        longitude__lte=max_lon,
                    )

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        places = list(queryset)

        params = self.get_search_params()

        latitude = params["latitude"]
        longitude = params["longitude"]
        radius = params["radius"]

        if latitude is not None:
            earth_radius = 6371000

            lat1 = radians(latitude)
            lon1 = radians(longitude)

            for place in places:
                lat2 = radians(float(place.latitude))
                lon2 = radians(float(place.longitude))

                dlat = lat2 - lat1
                dlon = lon2 - lon1

                a = (
                    sin(dlat / 2) ** 2
                    + cos(lat1) * cos(lat2)
                    * sin(dlon / 2) ** 2
                )

                a = min(1, max(0, a))

                distance = (
                    2 * earth_radius
                    * atan2(sqrt(a), sqrt(1 - a))
                )

                place.distance_meters = round(distance)

            places = [
                place for place in places
                if place.distance_meters <= radius
            ]

            places.sort(
                key=lambda place: place.distance_meters
            )

        else:
            places.sort(key=lambda place: place.name.lower())

        page = self.paginate_queryset(places)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(places, many=True)
        return Response(serializer.data)

