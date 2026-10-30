import requests
from django.conf import settings

# Verifikasi token reCAPTCHA
def verify_recaptcha(token):
    if not token or not settings.RECAPTCHA_SECRET_KEY:
        return False

    try:
        response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": settings.RECAPTCHA_SECRET_KEY, "response": token},
            timeout=5
        )
        response.raise_for_status()
        return response.json().get("success") is True
    except (requests.RequestException, ValueError):
        return False
