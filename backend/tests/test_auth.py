"""Autentikasi: hashing, sesi, dan cakupan perlindungan route."""

import pytest

from app.main import app
from app.services import auth

#: Route yang memang boleh diakses tanpa masuk, beserta alasannya.
TERBUKA = {
    "/health",  # dipakai Docker healthcheck, tidak membocorkan data
    "/api/auth/login",  # justru pintu masuknya
    "/api/auth/state",  # menjawab "apakah saya sudah masuk"
    "/api/auth/logout",  # keluar tidak boleh butuh sesi yang sah
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


class TestPassword:
    def test_hash_berbeda_untuk_password_sama(self):
        """Salt acak: dua akun dengan password sama tidak terlihat sama."""
        assert auth.hash_password("rahasia-panjang") != auth.hash_password("rahasia-panjang")

    def test_password_benar_diterima(self):
        assert auth.verify_password("rahasia-panjang", auth.hash_password("rahasia-panjang"))

    def test_password_salah_ditolak(self):
        assert not auth.verify_password("salah", auth.hash_password("rahasia-panjang"))

    def test_password_tidak_muncul_di_hash(self):
        assert "rahasia-panjang" not in auth.hash_password("rahasia-panjang")

    @pytest.mark.parametrize(
        "rusak", ["", "bukan-format", "bcrypt$1$2$3$4$5", "scrypt$a$b$c$d$e"]
    )
    def test_hash_rusak_ditolak_bukan_meledak(self, rusak):
        """Galat parsing tidak boleh menjadi jalan masuk."""
        assert auth.verify_password("apa pun", rusak) is False


class TestLogin:
    def test_kredensial_benar_memberi_sesi(self, anon_client):
        r = anon_client.post(
            "/api/auth/login", json={"username": "tester", "password": "kata-sandi-uji"}
        )

        assert r.status_code == 200
        assert r.json()["username"] == "tester"
        assert auth.COOKIE_NAME in r.cookies

    def test_password_salah_ditolak(self, anon_client):
        r = anon_client.post(
            "/api/auth/login", json={"username": "tester", "password": "salah"}
        )

        assert r.status_code == 401

    def test_pesan_sama_untuk_nama_salah_dan_password_salah(self, anon_client):
        """Pesan berbeda akan memberi tahu penebak nama mana yang terdaftar."""
        a = anon_client.post(
            "/api/auth/login", json={"username": "tester", "password": "salah"}
        ).json()
        b = anon_client.post(
            "/api/auth/login", json={"username": "hantu", "password": "salah"}
        ).json()

        assert a["detail"] == b["detail"]

    def test_cookie_tidak_dapat_dibaca_javascript(self, anon_client):
        r = anon_client.post(
            "/api/auth/login", json={"username": "tester", "password": "kata-sandi-uji"}
        )

        assert "httponly" in r.headers["set-cookie"].lower()

    def test_logout_membatalkan_sesi_di_server(self, client):
        assert client.get("/api/auth/me").status_code == 200

        client.post("/api/auth/logout")

        assert client.get("/api/auth/me").status_code == 401

    def test_token_disimpan_sebagai_hash_bukan_apa_adanya(self, anon_client):
        """Bocornya tabel sessions tidak boleh cukup untuk menyamar."""
        from app import models
        from app.db import get_db

        r = anon_client.post(
            "/api/auth/login", json={"username": "tester", "password": "kata-sandi-uji"}
        )
        token = r.cookies[auth.COOKIE_NAME]

        db = next(app.dependency_overrides[get_db]())
        tersimpan = [s.token_hash for s in db.query(models.SessionToken).all()]

        assert tersimpan and token not in tersimpan


class TestPerlindunganRoute:
    def test_seluruh_route_api_tertutup_tanpa_sesi(self, anon_client):
        """Yang terlupa dilindungi adalah yang bocor.

        Tes ini memindai tabel route sungguhan, sehingga endpoint baru yang
        ditambahkan tanpa autentikasi langsung membuat suite merah.
        """
        bocor = []
        for route in app.routes:
            path = getattr(route, "path", "")
            if path in TERBUKA or not path.startswith(("/api", "/health")):
                continue
            for metode in sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}):
                # Path parameter diisi nilai apa saja: yang diuji adalah apakah
                # permintaan ditolak SEBELUM sampai ke logika route.
                url = path.replace("{image_id}", "x").replace("{job_id}", "x")
                r = anon_client.request(metode, url)
                if r.status_code not in (401, 503):
                    bocor.append(f"{metode} {path} -> {r.status_code}")

        assert not bocor, "Route tanpa autentikasi: " + ", ".join(bocor)

    def test_tanpa_pengguna_terdaftar_api_menolak_bukan_membuka(self, anon_client):
        """Aplikasi yang terbuka karena pengaturannya belum selesai adalah
        persis keadaan yang hendak dihindari."""
        from app import models
        from app.db import get_db

        db = next(app.dependency_overrides[get_db]())
        db.query(models.SessionToken).delete()
        db.query(models.User).delete()
        db.commit()

        r = anon_client.get("/api/dashboard")

        assert r.status_code == 503
        assert "create_user" in r.json()["detail"]

    def test_health_tetap_terbuka(self, anon_client):
        """Healthcheck Docker berjalan tanpa sesi."""
        assert anon_client.get("/health").status_code == 200
