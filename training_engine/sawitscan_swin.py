"""Classifier tahap kedua: Swin Transformer atas potongan tajuk.

    modal deploy training_engine/sawitscan_swin.py

App terpisah dari mesin YOLOv8 dengan sengaja. Baseline deteksi sudah beku;
menambah kode ke app yang sama berarti setiap deploy Swin ikut membangun ulang
image detektornya, dan sesuatu yang sudah selesai tidak perlu ikut bergerak.

    POST /train                    mulai training, kembalikan job_id
    GET  /train/{job_id}/status    progres per epoch
    GET  /train/{job_id}/weights   unduh checkpoint terbaik
    POST /evaluate/{job_id}        ukur pada satu split

Checkpoint dipilih berdasarkan **macro F1 validation**, bukan accuracy. Dengan
`small` sekitar 3% dan `dead` di bawah 1% dari potongan, accuracy dapat tinggi
hanya dengan menebak kelas mayoritas, dan checkpoint yang terpilih justru yang
paling buta terhadap kelas minoritas.
"""

import hashlib
import json
import os
import shutil
import time
import zipfile
from pathlib import Path

import modal

APP_NAME = "sawitscan-swin"

volume = modal.Volume.from_name(f"{APP_NAME}-data", create_if_missing=True)
progress = modal.Dict.from_name(f"{APP_NAME}-progress", create_if_missing=True)

DATA_DIR = Path("/data")
DATASET_DIR = DATA_DIR / "datasets"
RUNS_DIR = DATA_DIR / "runs"

train_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "torch",
        "torchvision",
        "timm==1.0.20",
        "scikit-learn",
        "pillow",
    )
    .env({"HF_HOME": "/tmp/hf", "TIMM_HOME": "/tmp/timm"})
)

web_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "fastapi[standard]", "python-multipart"
)

app = modal.App(APP_NAME)

#: Varian yang boleh dipakai. Daftar tertutup: nilainya menjadi nama model yang
#: diunduh timm, jadi nilai bebas dari klien tidak boleh sampai ke sana.
MODELS = {
    "swin_tiny_patch4_window7_224",
    "swin_small_patch4_window7_224",
    "swin_base_patch4_window7_224",
}

MAX_EPOCHS = 100
GPU_TYPE = os.environ.get("SAWITSCAN_GPU", "L4")


def _tulis(job_id: str, **bidang) -> None:
    catatan = progress.get(job_id, {})
    catatan.update(bidang)
    catatan["updated_at"] = time.time()
    progress[job_id] = catatan


def _bongkar(zip_path: Path, tujuan: Path) -> Path:
    if tujuan.exists():
        shutil.rmtree(tujuan)
    tujuan.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        for anggota in zf.namelist():
            # Zip Slip: nama anggota dengan .. atau path absolut dapat menulis
            # ke luar folder tujuan.
            sasaran = (tujuan / anggota).resolve()
            if not str(sasaran).startswith(str(tujuan.resolve())):
                raise ValueError(f"Isi zip tidak wajar: {anggota}")
        zf.extractall(tujuan)
    if not (tujuan / "train").is_dir():
        raise ValueError("Arsip potongan harus berisi folder train/, val/, test/.")
    return tujuan


def _kelas(akar: Path) -> list[str]:
    """Urutan kelas dibaca dari classes.txt, tidak diserahkan ke urutan folder.

    ImageFolder mengurutkan folder secara alfabetis. Kebetulan urutannya sama di
    sini, tetapi menggantungkan pemetaan label pada kebetulan adalah cara paling
    senyap untuk menukar seluruh label dataset.
    """
    berkas = akar / "classes.txt"
    if not berkas.exists():
        raise ValueError("classes.txt tidak ada di arsip potongan.")
    return [b.strip() for b in berkas.read_text().splitlines() if b.strip()]


def _muat(akar: Path, split: str, kelas: list[str], latih: bool, batch: int):
    import torch
    from torchvision import datasets, transforms

    rerata = (0.485, 0.456, 0.406)
    simpangan = (0.229, 0.224, 0.225)

    if latih:
        ubah = transforms.Compose(
            [
                # Potongan sudah 224x224; RandomResizedCrop ringan memberi ragam
                # skala tanpa membuang tajuknya.
                transforms.RandomResizedCrop(224, scale=(0.7, 1.0), ratio=(0.85, 1.18)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomVerticalFlip(),
                # Tajuk dilihat dari atas: tidak ada arah "benar", jadi rotasi
                # penuh sah — berbeda dari citra sehari-hari.
                transforms.RandomRotation(180),
                transforms.ColorJitter(0.2, 0.2, 0.15, 0.03),
                transforms.ToTensor(),
                transforms.Normalize(rerata, simpangan),
            ]
        )
    else:
        ubah = transforms.Compose(
            [transforms.ToTensor(), transforms.Normalize(rerata, simpangan)]
        )

    data = datasets.ImageFolder(str(akar / split), transform=ubah)
    if list(data.classes) != list(kelas):
        raise ValueError(
            f"Urutan kelas {data.classes} tidak sama dengan classes.txt {kelas}."
        )
    return torch.utils.data.DataLoader(
        data,
        batch_size=batch,
        shuffle=latih,
        num_workers=4,
        pin_memory=True,
        drop_last=latih,
    )


def _metrik(y_benar, y_duga, kelas: list[str]) -> dict:
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

    p, r, f, dukungan = precision_recall_fscore_support(
        y_benar, y_duga, labels=list(range(len(kelas))), zero_division=0
    )
    makro_p, makro_r, makro_f, _ = precision_recall_fscore_support(
        y_benar, y_duga, labels=list(range(len(kelas))), average="macro", zero_division=0
    )
    cm = confusion_matrix(y_benar, y_duga, labels=list(range(len(kelas))))
    benar = sum(1 for a, b in zip(y_benar, y_duga) if a == b)

    return {
        "accuracy": benar / len(y_benar) if y_benar else 0.0,
        "macro_precision": float(makro_p),
        "macro_recall": float(makro_r),
        "macro_f1": float(makro_f),
        "per_class": {
            k: {
                "precision": float(p[i]),
                "recall": float(r[i]),
                "f1": float(f[i]),
                "support": int(dukungan[i]),
            }
            for i, k in enumerate(kelas)
        },
        # aktual -> prediksi
        "confusion": {
            k: {kelas[j]: int(cm[i][j]) for j in range(len(kelas))}
            for i, k in enumerate(kelas)
        },
    }


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
    model_name: str,
    run_name: str,
    lr: float = 1e-4,
    batch: int = 32,
) -> dict:
    """Latih Swin, pilih checkpoint terbaik menurut macro F1 validation."""
    import timm
    import torch
    import torch.nn as nn

    _tulis(
        job_id,
        status="running",
        epoch=0,
        total_epochs=epochs,
        history=[],
        started_at=time.time(),
        run_name=run_name,
        model_name=model_name,
    )

    try:
        volume.reload()
        akar = _bongkar(DATA_DIR / dataset_rel, Path("/tmp/crops") / job_id)
        kelas = _kelas(akar)

        latih = _muat(akar, "train", kelas, True, batch)
        sahih = _muat(akar, "val", kelas, False, batch)

        # Bobot kelas dihitung HANYA dari train. Menghitungnya dari val atau test
        # berarti membocorkan komposisi data uji ke dalam fungsi kerugian.
        jumlah = [0] * len(kelas)
        for _, t in latih.dataset.samples:
            jumlah[t] += 1
        total = sum(jumlah)
        bobot = torch.tensor(
            [total / (len(kelas) * maks) if maks else 0.0 for maks in jumlah],
            dtype=torch.float32,
        ).cuda()

        model = timm.create_model(model_name, pretrained=True, num_classes=len(kelas)).cuda()
        kerugian = nn.CrossEntropyLoss(weight=bobot, label_smoothing=0.05)
        optim = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.05)
        jadwal = torch.optim.lr_scheduler.OneCycleLR(
            optim, max_lr=lr, total_steps=epochs * len(latih), pct_start=0.1
        )
        skala = torch.amp.GradScaler("cuda")

        keluaran = RUNS_DIR / job_id
        keluaran.mkdir(parents=True, exist_ok=True)
        terbaik_f1 = -1.0
        riwayat = []

        for epoch in range(1, epochs + 1):
            model.train()
            rugi_total = 0.0
            for x, y in latih:
                x, y = x.cuda(non_blocking=True), y.cuda(non_blocking=True)
                optim.zero_grad(set_to_none=True)
                with torch.amp.autocast("cuda"):
                    rugi = kerugian(model(x), y)
                skala.scale(rugi).backward()
                skala.step(optim)
                skala.update()
                jadwal.step()
                rugi_total += rugi.item()

            model.eval()
            benar, duga = [], []
            with torch.no_grad():
                for x, y in sahih:
                    with torch.amp.autocast("cuda"):
                        keluar = model(x.cuda(non_blocking=True))
                    duga += keluar.argmax(1).cpu().tolist()
                    benar += y.tolist()

            m = _metrik(benar, duga, kelas)
            titik = {
                "epoch": epoch,
                "train_loss": round(rugi_total / max(1, len(latih)), 6),
                "val_accuracy": round(m["accuracy"], 6),
                "val_macro_f1": round(m["macro_f1"], 6),
                "val_macro_precision": round(m["macro_precision"], 6),
                "val_macro_recall": round(m["macro_recall"], 6),
                "val_f1_per_class": {k: round(v["f1"], 6) for k, v in m["per_class"].items()},
            }
            riwayat.append(titik)

            if m["macro_f1"] > terbaik_f1:
                terbaik_f1 = m["macro_f1"]
                torch.save(
                    {"model": model.state_dict(), "classes": kelas, "arch": model_name},
                    keluaran / "best.pt",
                )
                titik["saved"] = True

            _tulis(
                job_id,
                status="running",
                epoch=epoch,
                total_epochs=epochs,
                history=riwayat,
                latest=titik,
                best_val_macro_f1=round(terbaik_f1, 6),
            )

        bobot_berkas = keluaran / "best.pt"
        ringkasan = {
            "status": "done",
            "weights_bytes": bobot_berkas.stat().st_size,
            "weights_sha256": hashlib.sha256(bobot_berkas.read_bytes()).hexdigest(),
            "best_val_macro_f1": round(terbaik_f1, 6),
            "finished_at": time.time(),
        }
        (keluaran / "sawitscan.json").write_text(
            json.dumps({"history": riwayat, **ringkasan}, default=str), encoding="utf-8"
        )
        volume.commit()
        _tulis(job_id, **ringkasan)
        return ringkasan

    except Exception as exc:  # noqa: BLE001 — kegagalan apa pun harus terlihat
        _tulis(
            job_id,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            finished_at=time.time(),
        )
        raise


@app.function(
    image=train_image,
    gpu=GPU_TYPE,
    volumes={"/data": volume},
    timeout=60 * 60,
)
def evaluate_job(job_id: str, split: str = "test", batch: int = 64) -> dict:
    """Ukur checkpoint terbaik pada satu split."""
    import timm
    import torch

    volume.reload()
    berkas = RUNS_DIR / job_id / "best.pt"
    if not berkas.exists():
        raise FileNotFoundError(f"best.pt tidak ada untuk job {job_id}.")

    simpanan = torch.load(berkas, map_location="cuda", weights_only=False)
    kelas = simpanan["classes"]

    akar = _bongkar(DATASET_DIR / f"{job_id}.zip", Path("/tmp/eval") / job_id)
    if _kelas(akar) != kelas:
        raise ValueError("Urutan kelas dataset berbeda dengan checkpoint.")

    model = timm.create_model(simpanan["arch"], pretrained=False, num_classes=len(kelas))
    model.load_state_dict(simpanan["model"])
    model = model.cuda().eval()

    muat = _muat(akar, split, kelas, False, batch)
    benar, duga = [], []
    with torch.no_grad():
        for x, y in muat:
            with torch.amp.autocast("cuda"):
                keluar = model(x.cuda(non_blocking=True))
            duga += keluar.argmax(1).cpu().tolist()
            benar += y.tolist()

    return {
        "job_id": job_id,
        "split": split,
        "arch": simpanan["arch"],
        "weights_sha256": hashlib.sha256(berkas.read_bytes()).hexdigest(),
        "class_names": kelas,
        **_metrik(benar, duga, kelas),
    }


@app.function(
    image=web_image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("sawitscan-training-token")],
    max_containers=2,
)
@modal.asgi_app()
def web():
    import uuid

    from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
    from fastapi.responses import FileResponse
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    api = FastAPI(title="SawitScan Swin Classifier")
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
        import hmac

        diberikan = kredensial.credentials if kredensial else ""
        if not hmac.compare_digest(diberikan, harapan):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak sah.")

    @api.get("/health")
    def health() -> dict:
        return {"status": "ok", "gpu": GPU_TYPE}

    @api.post("/train", dependencies=[Depends(wajib_token)])
    async def mulai(
        dataset: UploadFile = File(...),
        epochs: int = Form(30),
        model_name: str = Form("swin_tiny_patch4_window7_224"),
        run_name: str = Form(""),
        lr: float = Form(1e-4),
        batch: int = Form(32),
    ) -> dict:
        if model_name not in MODELS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Model tidak dikenal. Pilihan: {', '.join(sorted(MODELS))}.",
            )
        if not 1 <= epochs <= MAX_EPOCHS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Epoch harus 1..{MAX_EPOCHS}."
            )

        job_id = uuid.uuid4().hex[:12]
        DATASET_DIR.mkdir(parents=True, exist_ok=True)
        tujuan = DATASET_DIR / f"{job_id}.zip"
        with tujuan.open("wb") as keluar:
            while potongan := await dataset.read(8 << 20):
                keluar.write(potongan)
        volume.commit()

        train_job.spawn(
            job_id,
            str(tujuan.relative_to(DATA_DIR)),
            epochs,
            model_name,
            run_name or job_id,
            lr,
            batch,
        )
        return {"job_id": job_id, "status": "queued", "run_name": run_name or job_id}

    @api.get("/train/{job_id}/status", dependencies=[Depends(wajib_token)])
    def status_training(job_id: str) -> dict:
        catatan = progress.get(job_id)
        if catatan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job tidak dikenal.")
        return {"job_id": job_id, **catatan}

    @api.post("/evaluate/{job_id}", dependencies=[Depends(wajib_token)])
    def evaluasi(job_id: str, split: str = "test") -> dict:
        if split not in {"train", "val", "test"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Split tidak dikenal.")
        try:
            return evaluate_job.remote(job_id, split)
        except FileNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    @api.get("/train/{job_id}/weights", dependencies=[Depends(wajib_token)])
    def unduh(job_id: str):
        volume.reload()
        berkas = RUNS_DIR / job_id / "best.pt"
        if not berkas.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Bobot belum tersedia.")
        return FileResponse(str(berkas), filename=f"swin-{job_id}.pt")

    return api
