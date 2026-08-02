"""Smoke test the whole API against a real PostgreSQL server.

The test suite runs on SQLite so it stays fast and dependency-free. This script is
the counterpart: it spins up a throwaway PostgreSQL (via `pgserver`, no Docker and
no system install), applies the migrations, and walks the full flow —
upload -> analyze -> results -> dashboard -> export.

    python scripts/check_postgres.py

Exits non-zero on the first failure.
"""

import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    try:
        import pgserver
    except ImportError:
        print("Butuh paket pgserver:  pip install pgserver", file=sys.stderr)
        return 1

    from PIL import Image

    data_dir = Path(tempfile.mkdtemp(prefix="sawitscan_pg_"))
    storage_dir = Path(tempfile.mkdtemp(prefix="sawitscan_store_"))
    server = pgserver.get_server(data_dir)

    try:
        os.environ["DATABASE_URL"] = server.get_uri().replace(
            "postgresql://", "postgresql+psycopg://"
        )
        os.environ["STORAGE_DIR"] = str(storage_dir)

        # Imported after the environment is set, so settings pick up this server.
        from alembic import command
        from alembic.config import Config
        from fastapi.testclient import TestClient

        os.chdir(BACKEND_ROOT)
        command.upgrade(Config("alembic.ini"), "head")

        from app.main import app

        client = TestClient(app)

        buffer = io.BytesIO()
        Image.new("RGB", (640, 480), "green").save(buffer, format="JPEG")

        uploaded = client.post(
            "/api/upload",
            files={"files": ("blok_a3_001.jpg", buffer.getvalue(), "image/jpeg")},
        )
        assert uploaded.status_code == 201, uploaded.text
        image_id = uploaded.json()["images"][0]["image_id"]
        print(f"upload        : OK ({image_id})")

        analyzed = client.post(f"/api/analyze/{image_id}")
        assert analyzed.status_code == 200, analyzed.text
        summary = analyzed.json()["summary"]
        assert summary["healthy"] + summary["infected"] == summary["total"]
        print(f"analyze       : OK {summary}")

        fetched = client.get(f"/api/results/{image_id}")
        assert fetched.json() == analyzed.json()
        print("results/{id}  : OK (identik dengan analyze)")

        listed = client.get("/api/results")
        assert listed.status_code == 200 and listed.json()[0]["status"] == "analyzed"
        print(f"results       : OK ({len(listed.json())} entri)")

        dashboard = client.get("/api/dashboard")
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["summary"]["total"] == summary["total"]
        print(f"dashboard     : OK {dashboard.json()['summary']}")

        for extension, prefix in (("csv", b"\xef\xbb\xbf"), ("pdf", b"%PDF-")):
            response = client.get(f"/api/results/{image_id}/export.{extension}")
            assert response.status_code == 200, response.text
            assert response.content.startswith(prefix)
            print(f"export {extension:<4}   : OK ({len(response.content)} bytes)")

        print("\nSeluruh alur berjalan di PostgreSQL.")
        return 0
    finally:
        server.cleanup()
        shutil.rmtree(data_dir, ignore_errors=True)
        shutil.rmtree(storage_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
