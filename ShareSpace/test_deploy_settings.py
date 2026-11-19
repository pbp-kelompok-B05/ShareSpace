"""Konfigurasi keamanan production di ShareSpace/settings.py.

Settings hanya dibaca sekali saat proses Python dimulai, jadi setiap kasus dijalankan di
subprocess dengan environment variable eksplisit. Variabel yang sudah ada di environment
tidak ditimpa load_dotenv(), sehingga isi file .env lokal tidak memengaruhi test ini.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent

PROBE = """
import json
from django.conf import settings
print(json.dumps({
    "DEBUG": settings.DEBUG,
    "SECRET_KEY": settings.SECRET_KEY,
    "SESSION_COOKIE_SECURE": settings.SESSION_COOKIE_SECURE,
    "CSRF_COOKIE_SECURE": settings.CSRF_COOKIE_SECURE,
}))
"""


class ProductionSettingsTest(SimpleTestCase):
    def load_settings(self, production, secret_key):
        env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "ShareSpace.settings",
            "PRODUCTION": "true" if production else "false",
            "SECRET_KEY": secret_key,
        }
        return subprocess.run(
            [sys.executable, "-c", "import django; django.setup()\n" + PROBE],
            cwd=BASE_DIR, env=env, capture_output=True, text=True, timeout=60,
        )

    def settings_for(self, production, secret_key):
        result = self.load_settings(production, secret_key)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_production_disables_debug_and_secures_cookies(self):
        loaded = self.settings_for(production=True, secret_key="kunci-rahasia-production-yang-panjang-dan-acak")
        self.assertFalse(loaded["DEBUG"])
        self.assertTrue(loaded["SESSION_COOKIE_SECURE"])
        self.assertTrue(loaded["CSRF_COOKIE_SECURE"])

    def test_production_uses_secret_key_from_environment(self):
        loaded = self.settings_for(production=True, secret_key="kunci-rahasia-production-yang-panjang-dan-acak")
        self.assertEqual(loaded["SECRET_KEY"], "kunci-rahasia-production-yang-panjang-dan-acak")

    def test_production_without_secret_key_refuses_to_start(self):
        result = self.load_settings(production=True, secret_key="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECRET_KEY", result.stderr)

    def test_local_development_keeps_debug_and_dev_key(self):
        loaded = self.settings_for(production=False, secret_key="")
        self.assertTrue(loaded["DEBUG"])
        self.assertTrue(loaded["SECRET_KEY"])
        self.assertFalse(loaded["SESSION_COOKIE_SECURE"])
