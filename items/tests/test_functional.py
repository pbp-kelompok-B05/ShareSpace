"""Functional test Selenium: alur utama Modul 2 di browser sungguhan.

Dilewati otomatis jika Chrome/driver tidak tersedia atau HTMX dari CDN tidak termuat
(offline). Kecualikan dengan --exclude-tag functional; SELENIUM_HEADED=1 menampilkan
jendela browser (untuk demo).
"""
import os
from unittest import SkipTest, mock

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import SimpleTestCase, tag
from django.urls import reverse
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.selenium_manager import SeleniumManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from items.models import Item

User = get_user_model()

PASSWORD = "PasswordTest123."
# Token unik di nama barang: katalog berisi data seed, jadi pencarian dipersempit ke token ini.
TOKEN = "Zqxsel"
WAIT_SECONDS = 10
MANAGER_TIMEOUT_SECONDS = 30


def find_chrome():
    """Path chromedriver dan Chrome lewat Selenium Manager, dengan batas waktu jaringan.

    Default Selenium Manager menunggu request jaringan sampai 300 detik dan tidak bisa
    diatur lewat webdriver.Chrome(); di sini dibatasi 30 detik (lalu memakai driver di
    cache jika ada) dan tanpa kirim statistik pemakaian.
    """
    paths = SeleniumManager().binary_paths([
        "--browser", "chrome", "--timeout", str(MANAGER_TIMEOUT_SECONDS), "--avoid-stats",
    ])
    return paths["driver_path"], paths["browser_path"]


def make_driver():
    driver_path, browser_path = find_chrome()
    options = webdriver.ChromeOptions()
    options.binary_location = browser_path
    if os.environ.get("SELENIUM_HEADED") != "1":
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    # style.css memakai scroll-behavior: smooth; tanpa ini Selenium mengklik sebelum scroll ke
    # elemen selesai (ElementClickInterceptedException). Mode reduced motion mematikan animasinya.
    options.add_argument("--force-prefers-reduced-motion")
    return webdriver.Chrome(service=ChromeService(executable_path=driver_path), options=options)


@tag("functional")
class CatalogFlowSeleniumTest(StaticLiveServerTestCase):
    # TransactionTestCase mem-flush DB setelah test; ini mengembalikan data seed sesudahnya.
    serialized_rollback = True

    @classmethod
    def setUpClass(cls):
        try:
            cls.driver = make_driver()
        except WebDriverException as exc:
            raise SkipTest(f"Chrome/driver Selenium tidak tersedia: {exc.msg or type(exc).__name__}")
        try:
            super().setUpClass()
        except Exception:
            cls.driver.quit()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(username="itemtest_selenium", password=PASSWORD)
        # Elemen di #item-list diganti HTMX, jadi referensi lama bisa stale saat ditunggu.
        self.wait = WebDriverWait(
            self.driver, WAIT_SECONDS,
            ignored_exceptions=[NoSuchElementException, StaleElementReferenceException],
        )

    def open(self, url_name, *args):
        self.driver.get(self.live_server_url + reverse(url_name, args=args))

    def require_htmx(self):
        if not self.driver.execute_script("return !!window.htmx"):
            self.skipTest("HTMX dari CDN tidak termuat (offline?)")

    def assertNoFullReload(self):
        self.assertTrue(self.driver.execute_script("return window.__noReload === true"))

    def login(self):
        self.open("authentication:login")
        login_url = self.driver.current_url
        self.driver.find_element(By.ID, "id_username").send_keys(self.user.username)
        self.driver.find_element(By.ID, "id_password").send_keys(PASSWORD)
        # Pilih lewat action form, bukan class styling, agar tahan terhadap desain ulang halaman login.
        login_path = reverse("authentication:login")
        self.driver.find_element(
            By.CSS_SELECTOR, f"form[action='{login_path}'] button[type='submit']",
        ).click()
        self.wait.until(EC.url_changes(login_url))

    def test_owner_adds_item_then_finds_it_in_catalog_without_reload(self):
        name = f"Termos Air {TOKEN} 1 Liter"
        self.login()

        # 1. Tambah barang lewat form (HTMX), lalu HX-Redirect ke detail dengan toast.
        self.open("items:create")
        self.require_htmx()
        self.driver.find_element(By.ID, "id_name").send_keys(name)
        self.driver.find_element(By.ID, "id_description").send_keys(
            "Termos stainless untuk bawa air minum ke kampus, tahan panas sampai enam jam."
        )
        Select(self.driver.find_element(By.ID, "id_category")).select_by_value(Item.Category.HOUSEHOLD)
        Select(self.driver.find_element(By.ID, "id_condition")).select_by_value(Item.Condition.GOOD)
        self.driver.find_element(By.CSS_SELECTOR, "#item-form button[type='submit']").click()

        title = self.wait.until(EC.visibility_of_element_located((By.ID, "item-title")))
        self.assertEqual(title.text, name)
        self.wait.until(EC.text_to_be_present_in_element((By.ID, "toast-region"), "berhasil ditambahkan"))
        item = Item.objects.get(name=name)
        self.assertEqual(item.owner, self.user)
        self.assertTrue(self.driver.current_url.endswith(reverse("items:detail", args=[item.pk])))

        # 2. Cari di katalog: hasil diganti HTMX tanpa reload, URL ikut diperbarui.
        self.open("items:catalog")
        self.driver.execute_script("window.__noReload = true")
        self.driver.find_element(By.ID, "id_q").send_keys(TOKEN)
        # Cocokkan persis: "51 barang ditemukan" (sebelum swap) juga memuat "1 barang ditemukan".
        self.wait.until(lambda d: d.find_element(
            By.CSS_SELECTOR, "#item-list .catalog-count",
        ).text == "1 barang ditemukan")
        titles = [el.text for el in self.driver.find_elements(By.CSS_SELECTOR, "#item-list .item-card-title")]
        self.assertEqual(titles, [name])
        self.wait.until(EC.url_contains(f"q={TOKEN}"))
        self.assertNoFullReload()

        # 3. Filter kategori lain digabung dengan pencarian: empty state "filter tanpa hasil".
        self.driver.find_element(By.XPATH, "//label[input[@name='category' and @value='sports']]").click()
        self.wait.until(EC.text_to_be_present_in_element((By.ID, "item-list"), "Tidak ada barang yang cocok"))
        self.wait.until(EC.url_contains("category=sports"))
        self.assertFalse(self.driver.find_elements(By.CSS_SELECTOR, "#item-list .item-card"))
        self.assertNoFullReload()


class SeleniumSkipTest(SimpleTestCase):
    """Tanpa Chrome/driver, test functional dilewati, bukan gagal."""

    def test_skips_when_driver_unavailable(self):
        error = WebDriverException("chromedriver tidak ditemukan")
        with mock.patch(f"{__name__}.make_driver", side_effect=error):
            with self.assertRaisesMessage(SkipTest, "chromedriver tidak ditemukan"):
                CatalogFlowSeleniumTest.setUpClass()

    def test_skips_when_selenium_manager_fails(self):
        # Mis. offline tanpa driver di cache: Selenium Manager gagal setelah batas waktu.
        error = WebDriverException("Unable to obtain driver for chrome")
        with mock.patch.object(SeleniumManager, "binary_paths", side_effect=error) as binary_paths:
            with self.assertRaises(SkipTest):
                CatalogFlowSeleniumTest.setUpClass()
        args = binary_paths.call_args.args[0]
        self.assertIn("--avoid-stats", args)
        self.assertEqual(args[args.index("--timeout") + 1], str(MANAGER_TIMEOUT_SECONDS))
