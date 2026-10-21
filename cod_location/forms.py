
from django import forms
from django.utils import timezone

from .models import CODLocation, PickupSchedule


class CODLocationForm(forms.ModelForm):
    class Meta:
        model = CODLocation
        fields = [
            "name",
            "address",
            "latitude",
            "longitude",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Contoh: Perpustakaan UI",
            }),
            "address": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Alamat atau deskripsi lokasi",
            }),
            "latitude": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "any",
                "id": "id_latitude",
            }),
            "longitude": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "any",
                "id": "id_longitude",
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Catatan tambahan (opsional)",
            }),
        }


# class PickupScheduleForm(forms.ModelForm):
#     class Meta:
#         model = PickupSchedule
#         fields = [
#             "cod_location",
#             "pickup_time",
#             "return_time",
#             "notes",
#         ]
#         widgets = {
#             "pickup_time": forms.DateTimeInput(attrs={
#                 "type": "datetime-local",
#                 "class": "form-control",
#             }),
#             "return_time": forms.DateTimeInput(attrs={
#                 "type": "datetime-local",
#                 "class": "form-control",
#             }),
#             "notes": forms.Textarea(attrs={
#                 "class": "form-control",
#                 "rows": 3,
#             }),
#         }

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields["cod_location"].queryset = (
#             CODLocation.objects.all()
#         )

#     def clean(self):
#         cleaned_data = super().clean()
#         pickup = cleaned_data.get("pickup_time")
#         returned = cleaned_data.get("return_time")

#         if pickup and returned:
#             if returned <= pickup:
#                 self.add_error(
#                     "return_time",
#                     "Waktu pengembalian harus setelah pengambilan.",
#                 )

#             if pickup < timezone.now():
#                 self.add_error(
#                     "pickup_time",
#                     "Jadwal pengambilan tidak boleh di masa lalu.",
#                 )

#         return cleaned_data
