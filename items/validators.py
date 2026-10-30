from django.core.validators import MinLengthValidator


class StrippedMinLengthValidator(MinLengthValidator):
    """MinLengthValidator yang menghitung panjang setelah spasi di tepi dibuang."""

    def clean(self, x):
        return len(x.strip())
