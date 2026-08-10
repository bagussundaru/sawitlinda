"""Mesin inference YOLOv8 di GPU Modal.

    modal deploy training_engine/sawitscan_inference.py

Ada karena VM produksi tidak punya GPU. Satu bingkai UAV 4000x2250 px dipotong
menjadi ~60 ubin, dan pada 2 vCPU itu memakan ±47 detik.

RANCANGAN: layanan ini SENGAJA dibuat sedangkal mungkin — ia hanya memotong
ubin yang sudah ditentukan pemanggil, menjalankan model, dan mengembalikan kotak
mentah. Geometri ubin, penggabungan NMS, pemetaan kelas ke kondisi, aturan
keparahan, dan georeferensi semuanya tetap di backend.

Alasannya: bila logika itu digandakan di sini, dua salinan akan berbeda begitu
salah satunya disunting, dan hasil di layar akan bergantung pada mesin mana yang
kebetulan dipakai. Satu-satunya hal yang berpindah ke GPU adalah perkalian
matriksnya.

Dua route, keduanya memerlukan `Authorization: Bearer <token>`:

    POST /model               unggah berkas bobot; dikunci menurut sha256-nya
    GET  /model/{sha}         apakah bobot itu sudah ada di sini
    POST /detect              citra + daftar ubin -> kotak mentah
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import modal

APP_NAME = "sawitscan-inference"

# Volume yang sama dengan mesin training, sehingga bobot hasil training dapat
# langsung dipakai tanpa disalin bolak-balik.
volume = modal.Volume.from_name("sawitscan-training-data", create_if_missing=True)

DATA_DIR = Path("/data")
MODEL_DIR = DATA_DIR / "weights"

GPU_TYPE = os.environ.get("SAWITSCAN_INFER_GPU", "L4")

inference_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libglib2.0-0")
    .pip_install(
        "ultralytics==8.4.115",
        "opencv-python-headless",
        "torch",
        "torchvision",
        "pillow",
    )
    .env(
        {
            "YOLO_AUTOINSTALL": "false",
            "ULTRALYTICS_AUTOINSTALL": "false",
            "YOLO_OFFLINE": "true",
            "YOLO_CONFIG_DIR": "/tmp/ultralytics",
        }
    )
)

web_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "fastapi[standard]", "python-multipart"
)

app = modal.App(APP_NAME)


@app.cls(
    image=inference_image,
    gpu=GPU_TYPE,
    volumes={"/data": volume},
    # Container tetap hidup sebentar setelah permintaan terakhir. Memuat model
    # ke GPU memakan beberapa detik; tanpa ini, tiap citra membayar ongkos itu
    # lagi dan keunggulan GPU habis oleh waktu penyalaan.
    scaledown_window=300,
    timeout=900,
)
class Detector:
    """Model ditahan di memori GPU antarpermintaan."""

    def __init__(self) -> None:
        self._model = None
        self._sha = None

    def _muat(self, sha: str):
        from ultralytics import YOLO

        if self._model is not None and self._sha == sha:
            return self._model

        volume.reload()
        berkas = MODEL_DIR / f"{sha}.pt"
        if not berkas.exists():
            raise FileNotFoundError(
                f"Bobot {sha[:12]} belum diunggah ke mesin inference."
            )
        self._model = YOLO(str(berkas))
        self._sha = sha
        return self._model

    @modal.method()
    def detect(
        self,
        image_bytes: bytes,
        tiles: list[list[int]],
        model_sha: str,
        imgsz: int = 512,
        conf: float = 0.25,
        iou: float = 0.45,
    ) -> dict:
        """Jalankan model pada ubin yang diminta.

        `tiles` adalah daftar [kiri, atas, kanan, bawah] dalam koordinat bingkai
        penuh, ditentukan pemanggil. Kotak dikembalikan dalam koordinat bingkai
        penuh juga — pergeserannya ditambahkan di sini karena di sinilah
        diketahui kotak mana berasal dari ubin mana.
        """
        import io

        from PIL import Image

        model = self._muat(model_sha)

        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGB")
            lebar, tinggi = img.size
            potongan = [img.crop(tuple(t)) for t in tiles]

        kotak: list[list] = []
        for mulai in range(0, len(potongan), 32):
            kelompok = potongan[mulai : mulai + 32]
            letak = tiles[mulai : mulai + 32]
            hasil = model.predict(
                source=kelompok, conf=conf, iou=iou, imgsz=imgsz, verbose=False
            )
            for frame, (kiri, atas, _, _) in zip(hasil, letak):
                for k in frame.boxes:
                    x1, y1, x2, y2 = k.xyxy[0].tolist()
                    kotak.append(
                        [
                            x1 + kiri,
                            y1 + atas,
                            x2 + kiri,
                            y2 + atas,
                            # Nama kelas, bukan indeksnya: indeks bergantung
                            # pada urutan di berkas model, dan menyamakannya
                            # antara dua mesin adalah kekeliruan yang menunggu
                            # terjadi.
                            model.names[int(k.cls.item())],
                            float(k.conf.item()),
                        ]
                    )

        return {
            "boxes": kotak,
            "width": lebar,
            "height": tinggi,
            "tiles": len(tiles),
            "names": list(model.names.values()),
        }


@app.function(
    image=web_image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("sawitscan-training-token")],
    max_containers=4,
)
@modal.asgi_app()
def web():
    import hmac
    import json

    from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    api = FastAPI(title="SawitScan Inference Engine")
    skema = HTTPBearer(auto_error=False)

    def wajib_token(
        kredensial: HTTPAuthorizationCredentials | None = Depends(skema),
    ) -> None:
        harapan = os.environ.get("SAWITSCAN_TRAINING_TOKEN", "")
        if not harapan:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Token belum dikonfigurasi pada secret Modal.",
            )
        diberikan = kredensial.credentials if kredensial else ""
        if not hmac.compare_digest(diberikan, harapan):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak sah.")

    @api.get("/health")
    def health() -> dict:
        return {"status": "ok", "gpu": GPU_TYPE}

    @api.get("/model/{sha}", dependencies=[Depends(wajib_token)])
    def punya_model(sha: str) -> dict:
        """Ditanyakan sebelum mengunggah; bobot 50 MB tidak perlu dikirim ulang."""
        volume.reload()
        return {"present": (MODEL_DIR / f"{sha}.pt").exists()}

    @api.post("/model", dependencies=[Depends(wajib_token)])
    async def unggah_model(weights: UploadFile = File(...)) -> dict:
        """Simpan berkas bobot, dikunci menurut sha256 isinya.

        Dikunci menurut isi, bukan nama: dua model berbeda bernama best.pt
        adalah keadaan yang wajar, dan menimpanya akan membuat hasil berubah
        diam-diam.
        """
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        pencerna = hashlib.sha256()
        sementara = MODEL_DIR / "unggah.part"
        with sementara.open("wb") as keluar:
            while potongan := await weights.read(4 * 1024 * 1024):
                pencerna.update(potongan)
                keluar.write(potongan)

        sha = pencerna.hexdigest()
        sementara.replace(MODEL_DIR / f"{sha}.pt")
        volume.commit()
        return {"sha256": sha, "bytes": (MODEL_DIR / f"{sha}.pt").stat().st_size}

    @api.post("/detect", dependencies=[Depends(wajib_token)])
    async def detect(
        image: UploadFile = File(...),
        tiles: str = Form(..., description="JSON: [[kiri,atas,kanan,bawah], …]"),
        model_sha: str = Form(...),
        imgsz: int = Form(512),
        conf: float = Form(0.25),
        iou: float = Form(0.45),
    ) -> dict:
        try:
            daftar_ubin = json.loads(tiles)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Daftar ubin tidak sah: {exc}"
            ) from exc
        if not isinstance(daftar_ubin, list) or not daftar_ubin:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Daftar ubin kosong.")
        if len(daftar_ubin) > 2000:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Terlalu banyak ubin ({len(daftar_ubin)}); batas 2000.",
            )

        isi = await image.read()
        try:
            return Detector().detect.remote(
                image_bytes=isi,
                tiles=daftar_ubin,
                model_sha=model_sha,
                imgsz=imgsz,
                conf=conf,
                iou=iou,
            )
        except FileNotFoundError as exc:
            # Backend menangkap ini dan mengunggah bobotnya, lalu mencoba lagi.
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    return api
