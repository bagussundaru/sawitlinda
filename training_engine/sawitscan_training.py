"""Mesin training YOLOv8 sebagai Modal App permanen.

Menggantikan notebook interaktif dengan layanan yang dapat dipanggil aplikasi:

    modal deploy training_engine/sawitscan_training.py

Tiga route, seluruhnya memerlukan header `Authorization: Bearer <token>`:

    POST /train                    mulai training, kembalikan job_id
    GET  /train/{job_id}/status    progres terkini per epoch
    GET  /train/{job_id}/weights   unduh best.pt
    POST /evaluate/{job_id}        ukur best.pt pada satu split (default test)

Progres ditulis ke modal.Dict lewat callback ultralytics tiap epoch — bukan
diambil dari stdout. stdout milik container GPU tidak dapat dibaca endpoint web
yang berjalan di container lain, dan formatnya berubah antar versi ultralytics.
"""

import hashlib
import json
import os
import shutil
import time
import zipfile
from pathlib import Path

import modal

APP_NAME = "sawitscan-training"

# --- Penyimpanan bersama ---------------------------------------------------
# Volume menampung dataset yang diunggah dan hasil training. Dict menampung
# progres: ia dapat ditulis dari container GPU dan dibaca container web dalam
# hitungan milidetik, sementara Volume perlu commit/reload.
volume = modal.Volume.from_name(f"{APP_NAME}-data", create_if_missing=True)
progress = modal.Dict.from_name(f"{APP_NAME}-progress", create_if_missing=True)

DATA_DIR = Path("/data")
DATASET_DIR = DATA_DIR / "datasets"
RUNS_DIR = DATA_DIR / "runs"

# --- Image -----------------------------------------------------------------
# opencv-python-headless: image ini tidak punya X11, dan opencv biasa gagal
# diimpor dengan "libGL.so.1: cannot open shared object file".
train_image = (
    modal.Image.debian_slim(python_version="3.11")
    # OpenCV — ditarik ultralytics — menautkan libGL dan libglib secara dinamis.
    # Keduanya tidak ada di debian_slim, dan ketiadaannya baru terlihat saat
    # `import ultralytics` di container GPU, bukan saat image dibangun.
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "ultralytics==8.4.115",
        "opencv-python-headless",
        "torch",
        "torchvision",
    )
    .env(
        {
            # Ultralytics memasang paket sendiri saat runtime bila merasa perlu,
            # dan pernah merusak Pillow di tengah training. Matikan.
            "YOLO_AUTOINSTALL": "false",
            "ULTRALYTICS_AUTOINSTALL": "false",
            "YOLO_OFFLINE": "false",  # bobot dasar yolov8*.pt masih perlu diunduh
            "YOLO_CONFIG_DIR": "/tmp/ultralytics",
        }
    )
)

web_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "fastapi[standard]", "python-multipart"
)

app = modal.App(APP_NAME)

#: Bobot dasar yang boleh dipakai. Daftar tertutup: nilai ini menjadi nama
#: berkas yang diunduh ultralytics, jadi nilai bebas dari klien tidak boleh
#: sampai ke sana.
BASE_MODELS = {"yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt"}

MAX_EPOCHS = 300
GPU_TYPE = os.environ.get("SAWITSCAN_GPU", "L4")


# --- Progres ---------------------------------------------------------------
def _tulis(job_id: str, **bidang) -> None:
    """Perbarui catatan progres. Dibaca endpoint status apa adanya."""
    catatan = progress.get(job_id, {})
    catatan.update(bidang)
    catatan["updated_at"] = time.time()
    progress[job_id] = catatan


def _angka(nilai) -> float | None:
    """Tensor/np.float dari ultralytics jadi float biasa, atau None."""
    if nilai is None:
        return None
    try:
        return round(float(nilai), 6)
    except (TypeError, ValueError):
        return None


def _pasang_callback(model, job_id: str, total_epoch: int) -> None:
    """Catat metrik tiap epoch ke Dict.

    on_fit_epoch_end dipilih, bukan on_train_epoch_end: ia dipanggil SETELAH
    validasi, sehingga mAP untuk epoch itu sudah tersedia. on_train_epoch_end
    berjalan sebelum validasi dan mAP-nya masih milik epoch sebelumnya.
    """

    def catat(trainer) -> None:
        metrik = getattr(trainer, "metrics", None) or {}
        # Nama loss dibaca dari trainer, tidak diasumsikan: task selain deteksi
        # memakai nama lain, dan urutannya bukan hal yang boleh ditebak.
        nama_loss = list(getattr(trainer, "loss_names", []) or [])
        nilai_loss = list(getattr(trainer, "loss_items", []) or [])
        loss = {
            nama.replace("_loss", "") + "_loss": _angka(nilai)
            for nama, nilai in zip(nama_loss, nilai_loss)
        }

        epoch = int(getattr(trainer, "epoch", 0)) + 1  # ultralytics mulai dari 0
        titik = {
            "epoch": epoch,
            "box_loss": loss.get("box_loss"),
            "cls_loss": loss.get("cls_loss"),
            "dfl_loss": loss.get("dfl_loss"),
            "map50": _angka(metrik.get("metrics/mAP50(B)")),
            "map50_95": _angka(metrik.get("metrics/mAP50-95(B)")),
            "precision": _angka(metrik.get("metrics/precision(B)")),
            "recall": _angka(metrik.get("metrics/recall(B)")),
        }

        catatan = progress.get(job_id, {})
        riwayat = catatan.get("history", [])
        riwayat.append(titik)
        _tulis(
            job_id,
            status="running",
            epoch=epoch,
            total_epochs=total_epoch,
            history=riwayat,
            latest=titik,
        )

    model.add_callback("on_fit_epoch_end", catat)


# --- Dataset ---------------------------------------------------------------
def _bongkar_dataset(zip_path: Path, tujuan: Path) -> Path:
    """Ekstrak zip dan temukan data.yaml di dalamnya.

    Zip ekspor Roboflow kadang berisi satu folder pembungkus, kadang tidak.
    Daripada mengasumsikan salah satu, data.yaml dicari.
    """
    if tujuan.exists():
        shutil.rmtree(tujuan)
    tujuan.mkdir(parents=True)

    with zipfile.ZipFile(zip_path) as zf:
        for anggota in zf.namelist():
            # Zip Slip: nama anggota yang mengandung .. atau path absolut dapat
            # menulis ke luar folder tujuan.
            sasaran = (tujuan / anggota).resolve()
            if not str(sasaran).startswith(str(tujuan.resolve())):
                raise ValueError(f"Isi zip tidak wajar: {anggota}")
        zf.extractall(tujuan)

    kandidat = sorted(tujuan.rglob("data.yaml"), key=lambda p: len(p.parts))
    if not kandidat:
        raise ValueError(
            "data.yaml tidak ditemukan dalam zip. "
            "Pastikan dataset diekspor dalam format YOLOv8."
        )
    return kandidat[0]


def _perbaiki_path_dataset(data_yaml: Path) -> None:
    """Tulis ulang path di data.yaml menjadi absolut.

    Roboflow menulis `train: ../train/images`, relatif terhadap direktori kerja
    saat ekspor — bukan terhadap letak data.yaml. Di sini direktori kerjanya
    berbeda, dan ultralytics akan mencari di tempat yang salah.
    """
    akar = data_yaml.parent
    baris_baru = []
    for baris in data_yaml.read_text(encoding="utf-8").splitlines():
        kunci = baris.split(":", 1)[0].strip()
        if kunci in {"train", "val", "test"} and ":" in baris:
            nilai = baris.split(":", 1)[1].strip().strip("'\"")
            if nilai and not Path(nilai).is_absolute():
                calon = (akar / nilai.lstrip("./")).resolve()
                if not calon.exists():  # ../train/images -> train/images
                    calon = (akar / Path(nilai).name).resolve()
                baris = f"{kunci}: {calon}"
        baris_baru.append(baris)
    data_yaml.write_text("\n".join(baris_baru) + "\n", encoding="utf-8")


# --- Training ---------------------------------------------------------------
@app.function(
    image=train_image,
    gpu=GPU_TYPE,
    volumes={"/data": volume},
    timeout=6 * 60 * 60,
)
def train_job(
    job_id: str,
    dataset_rel: str,
    epochs: int,
    base_model: str,
    run_name: str,
    imgsz: int = 640,
    batch: int = 16,
) -> dict:
    """Jalankan training YOLOv8 dan kembalikan metrik akhir.

    Dipanggil lewat .spawn() sehingga endpoint /train dapat langsung menjawab.
    """
    from ultralytics import YOLO

    _tulis(
        job_id,
        status="running",
        epoch=0,
        total_epochs=epochs,
        history=[],
        started_at=time.time(),
        run_name=run_name,
        base_model=base_model,
    )

    try:
        volume.reload()
        zip_path = DATA_DIR / dataset_rel
        if not zip_path.exists():
            raise FileNotFoundError(f"Dataset tidak ditemukan: {dataset_rel}")

        kerja = Path("/tmp/dataset") / job_id
        data_yaml = _bongkar_dataset(zip_path, kerja)
        _perbaiki_path_dataset(data_yaml)

        model = YOLO(base_model)
        _pasang_callback(model, job_id, epochs)

        model.train(
            data=str(data_yaml),
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            project=str(RUNS_DIR),
            name=job_id,
            exist_ok=True,
            verbose=True,
        )

        best = RUNS_DIR / job_id / "weights" / "best.pt"
        if not best.exists():
            raise FileNotFoundError("Training selesai tetapi best.pt tidak dihasilkan.")

        catatan = progress.get(job_id, {})
        terakhir = catatan.get("latest", {})
        ringkasan = {
            "status": "done",
            "weights_path": str(best.relative_to(DATA_DIR)),
            "weights_bytes": best.stat().st_size,
            "finished_at": time.time(),
            "final": terakhir,
        }
        (RUNS_DIR / job_id / "sawitscan.json").write_text(
            json.dumps({**catatan, **ringkasan}, default=str), encoding="utf-8"
        )
        volume.commit()
        _tulis(job_id, **ringkasan)
        return ringkasan

    except Exception as exc:  # noqa: BLE001 — kegagalan apa pun harus terlihat
        # Tanpa ini job yang gagal menggantung di status "running" selamanya dan
        # aplikasi memutar spinner tanpa akhir.
        _tulis(job_id, status="failed", error=f"{type(exc).__name__}: {exc}",
               finished_at=time.time())
        raise


@app.function(
    image=train_image,
    gpu=GPU_TYPE,
    volumes={"/data": volume},
    timeout=60 * 60,
)
def evaluate_job(job_id: str, split: str = "test", imgsz: int = 640) -> dict:
    """Ukur `best.pt` pada satu split, dan kembalikan angkanya apa adanya.

    Dijalankan terpisah dari training dengan sengaja. Test set hanya disentuh
    setelah checkpoint dipilih dari validation; menggabungkannya ke akhir
    training akan membuat angka test ikut terlihat pada setiap percobaan.

    Jumlah instance dihitung dari berkas label, bukan diambil dari ultralytics:
    namanya berpindah-pindah antar versi, sementara isi labelnya tidak.
    """
    import collections

    import yaml
    from ultralytics import YOLO

    volume.reload()
    bobot = RUNS_DIR / job_id / "weights" / "best.pt"
    if not bobot.exists():
        raise FileNotFoundError(f"best.pt tidak ada untuk job {job_id}.")

    kerja = Path("/tmp/eval") / job_id
    data_yaml = _bongkar_dataset(DATASET_DIR / f"{job_id}.zip", kerja)
    _perbaiki_path_dataset(data_yaml)

    nama_kelas = yaml.safe_load(data_yaml.read_text())["names"]

    hasil = YOLO(str(bobot)).val(
        data=str(data_yaml), split=split, imgsz=imgsz, verbose=False
    )

    # AP per kelas hanya berisi kelas yang muncul; `ap_class_index` memetakannya
    # kembali ke indeks kelas yang sebenarnya.
    ap50 = {}
    ap = {}
    for posisi, indeks in enumerate(hasil.box.ap_class_index):
        ap50[nama_kelas[int(indeks)]] = float(hasil.box.ap50[posisi])
        ap[nama_kelas[int(indeks)]] = float(hasil.box.maps[int(indeks)])

    instance: collections.Counter = collections.Counter()
    folder = {"train": "train", "val": "valid", "test": "test"}.get(split, split)
    for berkas in (data_yaml.parent / folder / "labels").glob("*.txt"):
        for baris in berkas.read_text().splitlines():
            bagian = baris.split()
            if bagian:
                instance[nama_kelas[int(float(bagian[0]))]] += 1

    return {
        "job_id": job_id,
        "split": split,
        "imgsz": imgsz,
        "weights_sha256": hashlib.sha256(bobot.read_bytes()).hexdigest(),
        "map50": float(hasil.box.map50),
        "map50_95": float(hasil.box.map),
        "precision": float(hasil.box.mp),
        "recall": float(hasil.box.mr),
        "per_class": {
            k: {
                "ap": ap50.get(k),
                "ap50_95": ap.get(k),
                "instances": instance.get(k, 0),
            }
            for k in nama_kelas
        },
        "class_names": list(nama_kelas),
    }


# --- Endpoint web ------------------------------------------------------------
@app.function(
    image=web_image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name(f"{APP_NAME}-token")],
    max_containers=2,
)
@modal.asgi_app()
def web():
    import uuid

    from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
    from fastapi.responses import FileResponse
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    api = FastAPI(title="SawitScan Training Engine")
    skema = HTTPBearer(auto_error=False)

    def wajib_token(
        kredensial: HTTPAuthorizationCredentials | None = Depends(skema),
    ) -> None:
        """Tanpa ini, siapa pun yang tahu URL dapat memicu training berulang dan
        menghabiskan kuota GPU."""
        harapan = os.environ.get("SAWITSCAN_TRAINING_TOKEN", "")
        if not harapan:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Token belum dikonfigurasi pada secret Modal.",
            )
        diberikan = kredensial.credentials if kredensial else ""
        # compare_digest: perbandingan biasa berhenti di karakter pertama yang
        # berbeda, dan selisih waktunya membocorkan token sedikit demi sedikit.
        import hmac

        if not hmac.compare_digest(diberikan, harapan):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak sah.")

    @api.get("/health")
    def health() -> dict:
        return {"status": "ok", "gpu": GPU_TYPE}

    @api.post("/train", dependencies=[Depends(wajib_token)])
    async def mulai_training(
        dataset: UploadFile = File(...),
        epochs: int = Form(50),
        base_model: str = Form("yolov8m.pt"),
        run_name: str = Form(""),
        imgsz: int = Form(640),
        batch: int = Form(16),
    ) -> dict:
        if base_model not in BASE_MODELS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Model dasar tidak dikenal. Pilihan: {', '.join(sorted(BASE_MODELS))}.",
            )
        if not 1 <= epochs <= MAX_EPOCHS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Jumlah epoch harus antara 1 dan {MAX_EPOCHS}.",
            )
        if not (dataset.filename or "").lower().endswith(".zip"):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Dataset harus berupa berkas .zip."
            )

        job_id = uuid.uuid4().hex[:12]
        DATASET_DIR.mkdir(parents=True, exist_ok=True)
        tujuan = DATASET_DIR / f"{job_id}.zip"

        # Disalin bertahap: dataset bisa ratusan MB dan membacanya sekaligus ke
        # memori akan mematikan container web.
        with tujuan.open("wb") as keluar:
            while potongan := await dataset.read(4 * 1024 * 1024):
                keluar.write(potongan)
        volume.commit()

        _tulis(
            job_id,
            status="queued",
            epoch=0,
            total_epochs=epochs,
            history=[],
            run_name=run_name or job_id,
            base_model=base_model,
            dataset_filename=dataset.filename,
            queued_at=time.time(),
        )

        panggilan = train_job.spawn(
            job_id=job_id,
            dataset_rel=f"datasets/{job_id}.zip",
            epochs=epochs,
            base_model=base_model,
            run_name=run_name or job_id,
            imgsz=imgsz,
            batch=batch,
        )
        _tulis(job_id, call_id=panggilan.object_id)

        return {
            "job_id": job_id,
            "status": "queued",
            "total_epochs": epochs,
            "base_model": base_model,
            "run_name": run_name or job_id,
        }

    @api.get("/train/{job_id}/status", dependencies=[Depends(wajib_token)])
    def status_training(job_id: str) -> dict:
        catatan = progress.get(job_id)
        if catatan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job tidak ditemukan.")
        return {"job_id": job_id, **catatan}

    @api.post("/evaluate/{job_id}", dependencies=[Depends(wajib_token)])
    def evaluasi(job_id: str, split: str = "test") -> dict:
        """Ukur best.pt pada satu split. Menunggu sampai selesai.

        Sengaja tidak diberi jalur `.spawn()`: hasilnya harus dibaca sekali dan
        dicatat, bukan dipantau berulang-ulang sampai angkanya terlihat bagus.
        """
        if split not in {"test", "val", "train"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Split tidak dikenal.")
        try:
            return evaluate_job.remote(job_id, split)
        except FileNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    @api.get("/train/{job_id}/weights", dependencies=[Depends(wajib_token)])
    def unduh_bobot(job_id: str):
        catatan = progress.get(job_id) or {}
        if catatan.get("status") != "done":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Training belum selesai (status: {catatan.get('status', 'tidak diketahui')}).",
            )
        volume.reload()
        berkas = DATA_DIR / catatan["weights_path"]
        if not berkas.exists():
            raise HTTPException(status.HTTP_410_GONE, "Berkas bobot sudah tidak ada.")
        return FileResponse(
            berkas,
            media_type="application/octet-stream",
            filename=f"{catatan.get('run_name', job_id)}-best.pt",
        )

    return api
