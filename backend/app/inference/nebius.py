"""Lapisan analisis AI lewat Nebius Token Factory (API kompatibel OpenAI).

APA YANG DILAKUKAN LAPISAN INI — dan yang tidak:

Model vision umum tidak dapat menggantikan YOLOv8 + Swin. Ia tidak bisa melokalisasi
puluhan pohon satu per satu dengan bounding box yang presisi. Yang bisa ia lakukan,
dan itu memang berguna, adalah menilai citra secara keseluruhan: kondisi apa yang
dominan, seberapa luas persoalannya, dan apa yang sebaiknya dikerjakan di lapangan.

Karena itu lapisan ini berjalan DI SAMPING deteksi, bukan menggantikannya. Deteksi
per pohon tetap keluar dari `run_inference()`; hasil di sini adalah pendapat kedua
pada tingkat citra, dan perbedaannya dengan hasil deteksi justru ditampilkan
apa adanya supaya operator tahu kapan harus memeriksa sendiri.

Kunci API dibaca dari environment (`NEBIUS_API_KEY`) dan tidak pernah ditulis
di berkas mana pun dalam repositori ini.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from PIL import Image

from app.config import Settings
from app.inference.conditions import CLASS_LABELS, CONDITIONS

logger = logging.getLogger("sawitscan.nebius")

#: Batas ukuran citra yang dikirim ke model. Bingkai UAV bisa puluhan MB;
#: mengirim utuh hanya memperlambat tanpa menambah ketelitian penilaian.
MAX_EDGE_PX = 1280


class NebiusError(RuntimeError):
    """Panggilan ke Nebius gagal. Selalu ditangkap pemanggil — analisis AI
    bersifat tambahan, kegagalannya tidak boleh menggagalkan deteksi."""


@dataclass
class AiAssessment:
    """Penilaian tingkat citra dari model vision."""

    summary: str
    dominant_condition: str
    #: 0..1, seberapa yakin model terhadap penilaiannya sendiri.
    confidence: float
    #: Perkiraan bagian tanaman yang bermasalah, 0..1.
    affected_share: float
    recommendation: str
    model: str
    #: "vision" bila model membaca citranya sendiri; "teks" bila model tidak
    #: menerima gambar dan penilaian dibuat dari ringkasan deteksi.
    mode: str = "vision"
    notes: list[str] = field(default_factory=list)


def _prompt() -> str:
    daftar = "\n".join(
        f"- {c.label} ({c.key}): {c.appearance} → {c.interpretation}" for c in CONDITIONS
    )
    label_valid = ", ".join(f'"{label}"' for label in CLASS_LABELS.values())

    return (
        "Anda adalah agronom kelapa sawit yang membaca citra udara (UAV) dari "
        "perkebunan. Nilai kondisi tajuk tanaman pada citra ini.\n\n"
        f"Kategori kondisi yang boleh dipakai:\n{daftar}\n\n"
        "Jawab HANYA dengan objek JSON, tanpa teks lain, dengan bentuk:\n"
        "{\n"
        f'  "dominant_condition": salah satu dari [{label_valid}],\n'
        '  "affected_share": angka 0..1 (perkiraan bagian tanaman yang bermasalah),\n'
        '  "confidence": angka 0..1 (keyakinan Anda sendiri terhadap penilaian ini),\n'
        '  "summary": 2-3 kalimat Bahasa Indonesia tentang apa yang terlihat,\n'
        '  "recommendation": 1-2 kalimat tindakan lapangan yang disarankan,\n'
        '  "notes": daftar string berisi keterbatasan pengamatan, boleh kosong\n'
        "}\n\n"
        "Kalau citra tidak jelas, beriringan awan, atau bukan citra perkebunan, "
        'katakan itu di "notes" dan turunkan "confidence".'
    )


#: Petunjuk pada jawaban galat bahwa model tidak menerima gambar.
TANDA_TANPA_VISI = ("image", "vision", "multimodal", "modality", "content type")


def _prompt_teks(ringkasan: dict) -> str:
    """Prompt untuk model yang tidak menerima gambar.

    Dinilai dari hasil deteksi, bukan dari citra. Bedanya nyata, jadi ikut
    ditandai pada hasil — supaya tidak dikira model melihat sendiri kebunnya.
    """
    per_kondisi = ringkasan.get("per_kondisi") or {}
    daftar = "\n".join(f"- {k}: {v} pohon" for k, v in per_kondisi.items())

    return (
        "Anda agronom kelapa sawit. Di bawah ini HASIL DETEKSI otomatis pada satu "
        "bingkai citra UAV. Anda TIDAK melihat citranya, hanya angkanya.\n\n"
        f"Total pohon terdeteksi: {ringkasan.get('total', 0)}\n"
        f"Sehat: {ringkasan.get('healthy', 0)}\n"
        f"Bermasalah: {ringkasan.get('infected', 0)}\n"
        f"Keparahan berat: {ringkasan.get('severe', 0)}\n"
        f"{daftar}\n\n"
        "Jawab HANYA dengan objek JSON, tanpa teks lain:\n"
        "{\n"
        '  "dominant_condition": kondisi terbanyak selain Sehat, atau "Sehat",\n'
        '  "affected_share": angka 0..1,\n'
        '  "confidence": angka 0..1,\n'
        '  "summary": 2-3 kalimat Bahasa Indonesia menafsirkan angka di atas,\n'
        '  "recommendation": 1-2 kalimat tindakan lapangan,\n'
        '  "notes": daftar string berisi keterbatasan\n'
        "}"
    )


def _encode_image(path: Path) -> str:
    """Kecilkan citra lalu jadikan data URL base64.

    Selalu dikirim ulang sebagai JPEG, jadi TIFF pun ikut tertangani.
    """
    buffer = io.BytesIO()
    with Image.open(path) as img:
        img = img.convert("RGB")
        if max(img.size) > MAX_EDGE_PX:
            img.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))
        img.save(buffer, format="JPEG", quality=85)

    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/jpeg;base64,{encoded}"


def _extract_json(text: str) -> dict:
    """Model kadang membungkus JSON dengan ```json atau kalimat pengantar."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    else:
        braces = re.search(r"\{.*\}", text, re.S)
        if braces:
            text = braces.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise NebiusError(f"Jawaban model bukan JSON yang sah: {text[:200]}") from exc


def _clamp(value, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _panggil(settings: Settings, messages: list) -> httpx.Response:
    url = settings.nebius_base_url.rstrip("/") + "/chat/completions"
    try:
        return httpx.post(
            url,
            json={
                "model": settings.nebius_model,
                "temperature": 0.2,
                "max_tokens": 700,
                "messages": messages,
            },
            headers={"Authorization": f"Bearer {settings.nebius_api_key}"},
            timeout=settings.nebius_timeout_s,
        )
    except httpx.HTTPError as exc:
        raise NebiusError(f"Tidak dapat menghubungi Nebius: {exc}") from exc


def assess_image(
    image_path: str, settings: Settings, summary: dict | None = None
) -> AiAssessment:
    """Minta penilaian tingkat citra dari model Nebius.

    Model yang menerima gambar membaca citranya sendiri. Model yang hanya
    menerima teks — DeepSeek dan sebagian besar model bahasa — tetap dapat
    dipakai: penilaian dibuat dari ringkasan deteksi, lalu ditandai
    `mode="teks"` agar tidak dikira model melihat sendiri kebunnya.

    Melempar NebiusError pada kegagalan apa pun; pemanggil menanganinya.
    """
    if not settings.ai_enabled:
        raise NebiusError("NEBIUS_API_KEY belum diisi.")

    path = Path(image_path)
    if not path.is_file():
        raise NebiusError("Berkas citra tidak ditemukan.")

    mode = "vision"
    response = _panggil(
        settings,
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _prompt()},
                    {"type": "image_url", "image_url": {"url": _encode_image(path)}},
                ],
            }
        ],
    )

    if response.status_code != 200:
        pesan = response.text[:400].lower()
        tanpa_visi = response.status_code in (400, 415, 422) and any(
            t in pesan for t in TANDA_TANPA_VISI
        )
        if not (tanpa_visi and summary):
            # Jangan pernah ikut menuliskan header Authorization ke log.
            raise NebiusError(
                f"Nebius menjawab {response.status_code}: {response.text[:200]}"
            )

        logger.info(
            "Model %s tampaknya tidak menerima gambar; beralih ke penilaian "
            "berbasis ringkasan deteksi.",
            settings.nebius_model,
        )
        mode = "teks"
        response = _panggil(settings, [{"role": "user", "content": _prompt_teks(summary)}])
        if response.status_code != 200:
            raise NebiusError(
                f"Nebius menjawab {response.status_code}: {response.text[:200]}"
            )

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise NebiusError("Bentuk jawaban Nebius tidak dikenali.") from exc

    data = _extract_json(content)

    labels = set(CLASS_LABELS.values())
    dominant = str(data.get("dominant_condition", "")).strip()
    if dominant not in labels:
        # Model kadang mengarang label; jangan diteruskan ke UI apa adanya.
        raise NebiusError(f"Model mengembalikan kondisi di luar daftar: {dominant!r}")

    notes = data.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]

    catatan = [str(n) for n in notes][:5]
    if mode == "teks":
        catatan.insert(
            0,
            "Model ini tidak menerima gambar. Penilaian dibuat dari ringkasan "
            "hasil deteksi, bukan dari citranya.",
        )

    return AiAssessment(
        summary=str(data.get("summary", "")).strip(),
        dominant_condition=dominant,
        confidence=_clamp(data.get("confidence")),
        affected_share=_clamp(data.get("affected_share")),
        recommendation=str(data.get("recommendation", "")).strip(),
        model=settings.nebius_model,
        mode=mode,
        notes=catatan[:6],
    )
