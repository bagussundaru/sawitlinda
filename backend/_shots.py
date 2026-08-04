"""Ambil screenshot tiap layar aplikasi untuk bahan presentasi."""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
OUT = Path("../docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)


def tunggu_peta(page, detik=25):
    """Peta hanya layak difoto setelah ubinnya benar-benar termuat."""
    batas = time.time() + detik
    while time.time() < batas:
        n = page.evaluate("document.querySelectorAll('.leaflet-tile-loaded').length")
        if n >= 4:
            time.sleep(1.5)
            return n
        time.sleep(0.7)
    return page.evaluate("document.querySelectorAll('.leaflet-tile-loaded').length")


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=2)

    def shot(name, path, wait=2.0, peta=False):
        page.goto(BASE + path, wait_until="networkidle")
        time.sleep(wait)
        if peta:
            n = tunggu_peta(page)
            print(f"    ubin peta: {n}")
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        print(f"  {name}.png")

    shot("01-dashboard", "/", 3.0, peta=True)
    shot("03-unggah", "/unggah", 2.0)
    shot("05-riwayat", "/riwayat", 2.5)
    shot("06-peta", "/peta", 3.0, peta=True)
    shot("07-laporan", "/laporan", 2.5)
    shot("08-pengaturan", "/pengaturan", 2.5)

    # Hasil deteksi
    page.goto(BASE + "/riwayat", wait_until="networkidle")
    time.sleep(2)
    href = page.eval_on_selector_all(
        "a[href^='/hasil/']", "els => els.length ? els[0].getAttribute('href') : null"
    )
    if href:
        page.goto(BASE + href, wait_until="networkidle")
        time.sleep(3)
        page.screenshot(path=str(OUT / "04-hasil-deteksi.png"), full_page=True)
        print("  04-hasil-deteksi.png")

    # Dashboard difilter ke satu blok, dengan satu pohon terpilih di peta
    page.goto(BASE + "/", wait_until="networkidle")
    time.sleep(2.5)
    tunggu_peta(page)
    for btn in page.query_selector_all("main button"):
        if (btn.inner_text() or "").strip() == "A-3":
            btn.click()
            break
    time.sleep(3.0)
    tunggu_peta(page)
    titik = page.query_selector_all(".leaflet-overlay-pane path")
    if titik:
        titik[len(titik) // 3].click()
        time.sleep(2.5)
    page.screenshot(path=str(OUT / "02-dashboard-blok.png"), full_page=True)
    print("  02-dashboard-blok.png")

    browser.close()
print("selesai")
