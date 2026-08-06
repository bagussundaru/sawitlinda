"""Buktikan model bekerja, memakai split uji dari dataset Roboflow itu sendiri.

Ini cara pembuktian yang paling kuat yang tersedia: citra kebun sungguhan yang
TIDAK pernah dilihat model saat pelatihan, lengkap dengan anotasi acuannya. Yang
keluar bukan sekadar "terlihat mendeteksi", melainkan mAP@50, presisi/recall per
kelas, dan confusion matrix — angka untuk bab hasil.

    # Unduh dari Roboflow: versi 3, format YOLOv8. Lalu:
    python scripts/validate_with_dataset.py ~/Downloads/dataset.zip

    # Batasi jumlah citra saat mencoba lebih dulu
    python scripts/validate_with_dataset.py dataset.zip --limit 20

    # Pakai split lain (test paling sahih; valid juga di luar data latih)
    python scripts/validate_with_dataset.py dataset.zip --split valid

Skrip ini mengunggah citra ke sistem, menganalisisnya, lalu mengirim arsip yang
SAMA ke /api/evaluate. Label untuk citra yang tidak diunggah otomatis terlewat,
jadi arsipnya tidak perlu dibongkar atau dikemas ulang.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

GAMBAR = {".jpg", ".jpeg", ".png"}


def _post(url: str, fields: dict[str, str], files: list[tuple[str, str, bytes]]) -> dict:
    """Kirim multipart/form-data memakai pustaka bawaan saja."""
    batas = f"----sawitscan{uuid.uuid4().hex}"
    bagian: list[bytes] = []

    for nama, nilai in fields.items():
        bagian.append(
            f'--{batas}\r\nContent-Disposition: form-data; name="{nama}"\r\n\r\n{nilai}\r\n'.encode()
        )
    for nama, berkas, isi in files:
        tipe = mimetypes.guess_type(berkas)[0] or "application/octet-stream"
        bagian.append(
            f'--{batas}\r\nContent-Disposition: form-data; name="{nama}"; '
            f'filename="{berkas}"\r\nContent-Type: {tipe}\r\n\r\n'.encode()
        )
        bagian.append(isi + b"\r\n")
    bagian.append(f"--{batas}--\r\n".encode())

    body = b"".join(bagian)
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={batas}"},
    )
    with urllib.request.urlopen(req, timeout=900) as resp:
        return json.loads(resp.read())


def _json(url: str, method: str = "GET") -> dict:
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=900) as resp:
        return json.loads(resp.read())


def _galat(exc: urllib.error.HTTPError) -> str:
    try:
        return json.loads(exc.read()).get("detail", str(exc))
    except Exception:
        return str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Arsip ekspor YOLOv8 dari Roboflow")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--split",
        default="test",
        help="Bagian dataset yang dipakai (default: test — di luar data latih)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Batasi jumlah citra")
    parser.add_argument("--block", default="UJI", help="Nama blok untuk citra uji")
    parser.add_argument("--iou", type=float, default=0.5, help="Ambang IoU evaluasi")
    args = parser.parse_args()

    base = args.url.rstrip("/")

    if not args.dataset.is_file():
        print(f"Berkas tidak ditemukan: {args.dataset}", file=sys.stderr)
        return 1

    try:
        sistem = _json(f"{base}/api/system")
    except Exception as exc:  # noqa: BLE001
        print(f"Tidak bisa menghubungi {base}: {exc}", file=sys.stderr)
        return 1

    print(f"Mesin inference : {sistem['inference_mode']}", end="")
    print(f" ({sistem.get('model_name')})" if sistem.get("model_name") else "")
    if sistem["inference_mode"] != "model":
        print(
            "\nPERINGATAN: sistem masih memakai mock. Angka yang keluar TIDAK\n"
            "mengukur model apa pun. Isi MODEL_PATH lebih dulu.\n",
            file=sys.stderr,
        )

    arsip = zipfile.ZipFile(args.dataset)
    citra = sorted(
        n
        for n in arsip.namelist()
        if Path(n).suffix.lower() in GAMBAR
        and f"/{args.split}/" in f"/{n}"
        and "label" not in n.lower()
    )
    if not citra:
        tersedia = sorted({p.split("/")[0] for p in arsip.namelist() if "/" in p})
        print(
            f"Tidak ada citra pada split '{args.split}'. Yang ada: {', '.join(tersedia)}",
            file=sys.stderr,
        )
        return 1

    if args.limit:
        citra = citra[: args.limit]

    print(f"Split '{args.split}' : {len(citra)} citra akan diuji\n")

    total_deteksi = 0
    total_detik = 0.0
    gagal = 0

    for i, anggota in enumerate(citra, start=1):
        nama = Path(anggota).name
        data = arsip.read(anggota)
        try:
            unggah = _post(
                f"{base}/api/upload",
                {"block": args.block},
                [("files", nama, data)],
            )
            image_id = unggah["images"][0]["image_id"]

            mulai = time.perf_counter()
            hasil = _json(f"{base}/api/analyze/{image_id}", method="POST")
            lama = time.perf_counter() - mulai
        except urllib.error.HTTPError as exc:
            print(f"  [{i}/{len(citra)}] {nama}: GAGAL — {_galat(exc)}")
            gagal += 1
            continue

        n = len(hasil["detections"])
        total_deteksi += n
        total_detik += lama
        ringkas = hasil["summary"]
        print(
            f"  [{i}/{len(citra)}] {nama[:28]:<28} {n:>3} deteksi "
            f"(sehat {ringkas['healthy']}, bermasalah {ringkas['infected']}) "
            f"· {lama:.2f}s"
        )

    berhasil = len(citra) - gagal
    if not berhasil:
        print("\nTidak ada citra yang berhasil dianalisis.", file=sys.stderr)
        return 1

    print(
        f"\nTotal {total_deteksi} deteksi pada {berhasil} citra "
        f"(rata-rata {total_deteksi / berhasil:.1f} per citra, "
        f"{total_detik / berhasil:.2f}s per citra)"
    )

    if total_deteksi == 0:
        print(
            "\nModel tidak mendeteksi apa pun pada citra kebun sungguhan.\n"
            "Itu temuan penting — periksa berkas model dan ambang keyakinannya.",
            file=sys.stderr,
        )

    print("\nMengevaluasi terhadap anotasi acuan dari arsip yang sama…")
    try:
        evaluasi = _post(
            f"{base}/api/evaluate",
            {"iou_threshold": str(args.iou)},
            [("file", args.dataset.name, args.dataset.read_bytes())],
        )
    except urllib.error.HTTPError as exc:
        print(f"Evaluasi gagal: {_galat(exc)}", file=sys.stderr)
        return 1

    print(
        f"\n{'':<14}mAP@50 {evaluasi['map50']:.3f}   "
        f"presisi {evaluasi['micro_precision']:.3f}   "
        f"recall {evaluasi['micro_recall']:.3f}   "
        f"F1 {evaluasi['micro_f1']:.3f}"
    )
    print(
        f"{'':<14}{evaluasi['images']} citra · {evaluasi['ground_truths']} anotasi acuan "
        f"· {evaluasi['predictions']} prediksi · IoU >= {evaluasi['iou_threshold']}\n"
    )

    print(f"{'kelas':<14}{'acuan':>7}{'TP':>6}{'FP':>6}{'FN':>6}{'presisi':>10}{'recall':>9}{'AP':>9}")
    for m in evaluasi["per_class"]:
        print(
            f"{m['label']:<14}{m['support']:>7}{m['true_positive']:>6}"
            f"{m['false_positive']:>6}{m['false_negative']:>6}"
            f"{m['precision']:>9.1%}{m['recall']:>9.1%}{m['average_precision']:>9.1%}"
        )

    print(f"\nMode saat evaluasi: {evaluasi['inference_mode']}")
    print("Hasil tersimpan dan dapat dibuka kembali di layar Evaluasi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
