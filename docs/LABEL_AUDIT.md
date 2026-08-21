# Audit Label — Phase A.5

Pemeriksaan dataset sebelum definisinya dibekukan. Tujuannya memastikan
**semantik label benar**, bukan mengukur performa model.

Sumber: `oil-palm-central-kalimantan` v3 (Roboflow), 1.007 citra, 67.829 kotak.
Seluruh angka di sini dihitung dari arsip dataset itu sendiri.

---

## 1. Pemetaan label

`data.yaml` menulis:

```
nc: 4
names: ['dead', 'healthy', 'small', 'yellow']
```

Urutan ini **berbeda** dari urutan tampilan di aplikasi
(`healthy, yellow, small, dead`). Perbedaan itu tidak berbahaya selama urutannya
selalu **dibaca**, bukan diasumsikan — dan sistem memang membacanya:
`app/inference/yolo.py` dari `model.names`, `app/evaluation/parsers.py` dan
`app/training/crops.py` dari `data.yaml`.

Bahaya asumsi itu nyata: satu skrip audit sekali-pakai pernah menebak urutannya,
seluruh kelas tertukar, dan angkanya tetap terlihat masuk akal sampai
`data.yaml` benar-benar dibuka. `crops.class_names()` karena itu **menolak**
arsip tanpa `names:` alih-alih memberi urutan bawaan.

Indeks yang benar-benar muncul di berkas label: `0, 1, 2, 3` — tidak ada indeks
liar, tidak ada variasi penulisan nama kelas.

---

## 2. Sebaran kelas

| Kelas | Kotak | % | Citra | Kelompok sumber |
| --- | ---: | ---: | ---: | ---: |
| healthy | 38.078 | 56,14% | 968 | 489 |
| yellow | 21.259 | 31,34% | 756 | 498 |
| small | 8.139 | 12,00% | 670 | 214 |
| **dead** | **353** | **0,52%** | 146 | 93 |
| **Total** | **67.829** | | 1.006 | 510 |

`healthy` mayoritas — wajar untuk perkebunan. `dead` kelas minoritas ekstrem.

Sebaran ini **cocok dengan yang diprediksi model di produksi** (healthy 67,6%,
yellow 20,8%, small 10,9%, dead 0,6%), sehingga tidak ada indikasi salah
pemetaan kelas pada model yang berjalan.

---

## 3. Dua populasi dalam satu dataset

| Sumber | Citra | dead | healthy | small | yellow |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ubin orthomosaic | 500 | 0,2% | 77,1% | 21,3% | 1,3% |
| Bingkai UAV berdiri sendiri | 507 | 0,8% | 36,7% | 3,4% | 59,2% |

Keduanya nyaris berlawanan. Setiap pembagian split yang mengabaikan jenis sumber
menghasilkan split yang mengukur populasi berbeda.

---

## 4. Kebocoran pada split bawaan

Ketiga mosaik tersebar ke **seluruh** split Roboflow:

| Mosaik | train | valid | test |
| --- | ---: | ---: | ---: |
| 44000_16000 | 97 | 50 | 36 |
| 52000_20000 | 90 | 49 | 34 |
| 44000_4000 | 73 | 41 | 30 |

**100 dari 176 citra split test (57%) berasal dari mosaik yang juga ada di
train.** Ubin bertetangga saling bersinggungan, sehingga pohon yang sama dapat
muncul di kedua sisi.

Konsekuensinya: `mAP@50 = 0,555` tidak layak disebut performa test yang bebas
kebocoran. Angka itu **dipertahankan sebagai catatan historis**, bukan dihapus:

```
baseline-yolov8-roboflow      mAP@50 = 0,555   status = historical / potentially leaked
baseline-yolov8-group-aware   mAP@50 = ?       status = akan diukur (Phase B)
```

---

## 5. Audit visual

Lembar contoh di [`label-audit/`](label-audit/), tiap potongan diberi nama citra
asal, indeks pohon, dan ukuran kotaknya.

| Berkas | Isi |
| --- | --- |
| `contoh-healthy.png` | 30 contoh dari 30 sumber berbeda |
| `contoh-yellow.png` | 30 contoh dari 30 sumber berbeda |
| `contoh-small.png` | 30 contoh dari 30 sumber berbeda |
| `contoh-dead.png` | 30 contoh dari 30 sumber berbeda |
| `dead-seluruhnya.png` | **seluruh 353** potongan `dead` |

Contoh diambil menyebar antar-kelompok sumber, bukan menumpuk pada satu citra —
30 potongan dari 30 sumber berbeda untuk tiap kelas.

### Pengamatan

**healthy** — tajuk hijau rapat, pelepah normal. Konsisten.

**yellow** — pelepah menguning atau hijau pucat terlihat jelas dan berbeda dari
`healthy`. Konsisten.

**dead** — sebagian besar tajuk cokelat mengering, pelepah mati. Beberapa
potongan tampak masih cukup hijau dan **layak ditandai ambigu** — lihat
`dead-seluruhnya.png` untuk memeriksa seluruhnya. Tidak ada yang dilabeli ulang;
pengamatan ini dicatat, bukan ditindaklanjuti.

**small** — tajuk hijau sehat, hanya berukuran kecil. Lihat bagian berikutnya.

---

## 6. `small` hampir seluruhnya dapat ditentukan dari ukuran saja

Sisi terpanjang kotak, dalam piksel:

| Kelas | n | p10 | median | p90 |
| --- | ---: | ---: | ---: | ---: |
| healthy | 38.075 | 44 | 54 | 68 |
| yellow | 21.256 | 39 | 55 | 78 |
| dead | 353 | 32 | 50 | 79 |
| **small** | **8.130** | **19** | **31** | **38** |

Aturan sepele "small bila sisi ≤ 38 px":

```
benar mengenali small : 7.467 dari 8.130   (91,8%)
keliru menyebut small : 3.842 dari 59.684  ( 6,4%)
```

Hanya **1,6%** potongan `small` yang lebih besar dari persentil 25 `healthy`.

### Artinya

`small` adalah **karakteristik ukuran**, bukan kondisi visual seperti `yellow`
dan `dead`. Secara visual, potongan `small` tampak seperti tajuk sehat yang
kecil.

Risikonya nyata untuk tahap Swin: bila potongan diperkecil ke ukuran masukan
tetap, ukuran absolut memang hilang — tetapi ketajaman gambar tidak. Potongan
31 px yang diperbesar ke 224 px jauh lebih buram daripada potongan 54 px, dan
model dapat mempelajari keburaman itu alih-alih kondisi tanaman.

### Yang akan dilakukan

Aturan ukuran di atas dijadikan **baseline sepele** yang harus dilampaui Swin.
Melaporkan "Swin mencapai F1 sekian" tanpa pembanding ini menyembunyikan
kemungkinan bahwa sebagian besar performanya berasal dari ukuran semata.

Tidak ada label yang diubah.

---

## 7. Status

| Pemeriksaan | Status |
| --- | --- |
| Pemetaan label | ✅ benar, dibaca bukan ditebak |
| Sebaran kelas | ✅ terdokumentasi |
| Sebaran sumber | ✅ dua populasi teridentifikasi |
| Audit kebocoran | ✅ kebocoran terbukti pada split bawaan |
| Perbandingan prediksi produksi | ✅ cocok dengan sebaran latih |
| Audit visual | ✅ lembar contoh tersedia |

**Definisi dataset dibekukan pada titik ini.** Keputusan yang menyertainya:

1. Split memakai **Opsi C** — bingkai UAV berdiri sendiri sebagai populasi
   val/test; ubin orthomosaic hanya sebagai data latih tambahan, dan statusnya
   disebut eksplisit pada setiap laporan.
2. `dead` dilaporkan apa adanya sebagai kelas minoritas, dengan keterbatasannya
   dinyatakan. Tidak digabung, tidak dikarang, tidak di-oversample sebelum ada
   penambahan anotasi yang sebenarnya.
3. `mAP@50 = 0,555` disimpan sebagai catatan historis yang berpotensi terkena
   kebocoran.
4. Aturan ukuran menjadi baseline pembanding untuk `small`.

Susunan split yang dipakai:

```
TRAIN       354 bingkai UAV  +  500 ubin orthomosaic
VALIDATION   76 bingkai UAV
TEST         76 bingkai UAV
```

Jangan dilaporkan sebagai "1.007 citra dibagi 70/15/15" — itu menyembunyikan
struktur dataset yang sebenarnya.


---

## 8. Phase B0 — dataset siap-latih

Dua arsip dibangun dari arsip Roboflow dengan `app/training/datasets.py`.
Tidak disimpan di repositori; dibangun ulang dari arsip sumber.

| | B1 | B2 |
| --- | --- | --- |
| Train | 354 bingkai UAV | 354 bingkai UAV + 500 ubin mosaik |
| Validation | 76 bingkai UAV | **sama persis** |
| Test | 76 bingkai UAV | **sama persis** |
| Kotak latih | 20.851 | 53.507 |
| Ukuran | 40,5 MB | 65,5 MB |
| Kebocoran | 0 kelompok | 0 kelompok |

Validation dan test **identik byte demi byte** antara keduanya (diverifikasi
lewat sha256 atas seluruh isinya). Tanpa itu, selisih angka B1 dan B2 tidak
dapat dikaitkan dengan data latih tambahan.

### Sebaran kelas

| Split | dead | healthy | small | yellow |
| --- | ---: | ---: | ---: | ---: |
| B1 train | 143 | 9.309 | 732 | 10.667 |
| B2 train | 221 | 34.496 | 7.689 | 11.101 |
| val | 72 | 1.857 | 180 | 5.087 |
| test | 60 | 1.725 | 270 | 5.071 |

Perhatikan B2: data latih tambahan menggeser sebarannya jauh dari val/test —
`healthy` naik dari 44,6% ke 64,5%, `yellow` turun dari 51,2% ke 20,7%. Itulah
justru yang hendak diuji: apakah tambahan data itu membantu, atau membawa
pergeseran domain.

Tiap arsip memuat `SPLIT.md` dan `split-manifest.csv`, sehingga cara
pembagiannya dapat dibaca tanpa bertanya kepada siapa pun.

### Belum dikerjakan

B1 dan B2 belum dilatih. Training memerlukan GPU, dan mesin training Modal
belum di-deploy (`MODAL_TRAINING_URL` masih kosong).
