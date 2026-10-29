from django.forms import ModelForm, DateInput, Textarea
from django.utils import timezone
from .models import LoanRequest

class LoanRequestForm(ModelForm):

    class Meta:
        model = LoanRequest
        fields = ["start_date", "due_date", "notes"]
        widgets = {
            "start_date": DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "due_date": DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "notes": Textarea(
                attrs={"rows": 3, "placeholder": "Tambahkan keterangan di sini"}
            )
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        due_date = cleaned_data.get("due_date")

        if start_date and start_date < timezone.localdate():
            if self.instance._state.adding or "start_date" in self.changed_data:
                self.add_error("start_date", "Tanggal mulai tidak boleh di masa lalu.")

        if start_date and due_date and due_date < start_date:
            self.add_error("due_date", "Tanggal selesai harus setelah atau sama dengan tanggal mulai.")

        return cleaned_data
