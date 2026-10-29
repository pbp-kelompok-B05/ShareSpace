
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
                "placeholder": "Alamat lokasi COD",
            }),

            "latitude": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "any",
                "id": "id_latitude",
                "readonly": True,
            }),

            "longitude": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "any",
                "id": "id_longitude",
                "readonly": True,
            }),

            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Catatan tambahan (opsional)",
            }),
        }


class PickupScheduleForm(forms.ModelForm):
    class Meta:
        model = PickupSchedule

        fields = [
            "cod_location",
            "schedule_type",
            "scheduled_time",
            "notes",
        ]

        widgets = {
            "cod_location": forms.Select(attrs={
                "class": "form-control",
            }),

            "schedule_type": forms.Select(attrs={
                "class": "form-control",
            }),

            "scheduled_time": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                }
            ),

            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Catatan pertemuan (opsional)",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["cod_location"].queryset = (
            CODLocation.objects.all()
        )

        self.fields["scheduled_time"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ]

    def clean_scheduled_time(self):
        scheduled_time = self.cleaned_data["scheduled_time"]

        if scheduled_time < timezone.now():
            raise forms.ValidationError(
                "Jadwal tidak boleh berada di masa lalu."
            )

        return scheduled_time



