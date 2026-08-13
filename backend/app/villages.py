"""Desa contoh di Kabupaten Kotawaringin Timur, Kalimantan Tengah.

Daftar tertutup, mengikuti lokasi pengambilan dataset penelitian. Dipakai
sebagai pengelompokan pada layar peta dan dashboard.

KOORDINAT DI SINI TIDAK DIPAKAI UNTUK MENEMPATKAN CITRA. Letak setiap citra di
peta berasal dari EXIF GPS-nya sendiri — nilai yang benar-benar terukur oleh
drone. Koordinat di bawah hanya menentukan ke mana peta bergeser saat sebuah
desa dipilih dan belum ada citra ber-GPS di dalamnya, dan sengaja ditandai
sebagai perkiraan pusat wilayah, bukan titik survei.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Village:
    key: str
    name: str
    district: str
    #: Perkiraan pusat wilayah, hanya untuk memposisikan tampilan peta.
    lat: float
    lng: float


VILLAGES: tuple[Village, ...] = (
    Village("parenggean", "Karang Tunggal / Parenggean", "Parenggean", -1.85, 112.95),
    Village("kota-besi", "Kota Besi", "Kota Besi", -2.35, 112.85),
    Village("terantang", "Terantang", "Seranau", -2.70, 112.98),
    Village("bapeang", "Bapeang", "Mentawa Baru Ketapang", -2.35, 112.75),
    Village("samuda", "Samuda", "Mentaya Hilir Selatan", -3.05, 112.95),
)

BY_KEY = {v.key: v for v in VILLAGES}

#: Perkiraan pusat kabupaten, dipakai saat belum ada citra ber-GPS sama sekali.
DISTRICT_CENTRE = (-2.45, 112.90)
DISTRICT_NAME = "Kotawaringin Timur, Kalimantan Tengah"


def is_valid(key: str | None) -> bool:
    return key is not None and key in BY_KEY


def label(key: str | None) -> str | None:
    village = BY_KEY.get(key or "")
    return village.name if village else None
