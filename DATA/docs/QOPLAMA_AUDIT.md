# QOPLAMA dataset — audit

Raximjon Soataliyev / NBA jamoasi bergan dataset. Joylashuvi: `DATA/raw/qoplama_tashkent/`
Manifest: `DATA/manifests/qoplama_tashkent.csv`

---

## 1. Nima bu

**1,141 ta rasm, 12 ta papka.** Har papka = bitta ASTM D6433 nuqson turi. Annotatsiya yo'q — papka nomi yagona yorliq (image-level classification).

Bu **ASTM taksonomiyasida tuzilgan birinchi datasetimiz** — RDD ning D00/D20 kodlari emas, to'g'ridan-to'g'ri standart atamalari. Bu qimmatli.

Telegramdagi xabar to'g'ri: *"19 ta nuqsondan eng ko'p uchraydigan 12 tasi bo'yicha dastlabki ma'lumotlar yig'ildi."*

---

## 2. Tarkibi — ikkita butunlay boshqa manba

Bu eng muhim topilma. Dataset bir jinsli emas:

| Manba | Soni | Nima |
|---|---|---|
| **`IMG_*.jpg`** | **278** | **Toshkentda yangi suratga olingan**, Xiaomi Redmi Note 14, GPS bilan, 2026-yil iyul |
| `Adachi_*`, `Numazu_*`, … | 863 | **RoadDamageDataset (Yaponiya) rasmlari**, ASTM turlari bo'yicha qayta saralangan |

Ya'ni datasetning **76% i — bizda allaqachon bor bo'lgan yapon rasmlari**, faqat boshqacha yorliqlangan. Yangi ma'lumot — 278 ta rasm.

---

## 3. Toshkent rasmlari (278 ta) — eng qimmatli qism

| Ko'rsatkich | Qiymat |
|---|---|
| Kamera | Xiaomi Redmi Note 14 |
| O'lcham | 4000×3000 (238 ta), 3000×4000 vertikal (40 ta) |
| GPS | **278/278 tasida bor** ✅ |
| Hudud | 41.2708–41.2823 N, 69.2874–69.3031 E → **~1.28 × 1.31 km, sharqiy Toshkent** |
| Sessiyalar | 11-iyul (228 ta), 28-iyul (50 ta) |

**Nega bu muhim:**
- **In-domain** — Toshkent asfalti, Toshkent yorug'ligi, Toshkent qurilish uslubi. Yaponiya yoki Tehron emas.
- **GPS bor** → xaritali demo to'g'ridan-to'g'ri quriladi
- **4000×3000** → RDD ning 600×600 idan **44 marta ko'p piksel**. Yorilish kengligini mm da o'lchash uchun aynan shu kerak.

**Cheklov:** hudud juda kichik (1.3 km²), ikki kunda olingan, bitta telefon. Bu — *namuna*, *korpus* emas.

---

## 4. Klasslar taqsimoti

| ASTM # | Klass | Birlik | Jami | Toshkent | RDD dan |
|---:|---|---|---:|---:|---:|
| 10 | longitudinal_transverse_cracking | m | 250 | 97 | 153 |
| 1 | alligator_cracking | m² | 157 | 59 | 98 |
| 4 | bumps_and_sags | m | 124 | 6 | 118 |
| 19 | weathering_raveling | m² | 118 | 5 | 113 |
| 7 | edge_cracking | m | 113 | 3 | 110 |
| 3 | block_cracking | m² | 100 | 60 | 40 |
| 11 | patching | m² | 100 | 19 | 81 |
| 12 | polished_aggregate | m² | 87 | 7 | 80 |
| 13 | potholes | dona | 53 | 6 | 47 |
| 15 | rutting | m² | 26 | 12 | 14 |
| 5 | corrugation | m² | 11 | 4 | 7 |
| 2 | bleeding | m² | 2 | 0 | 2 |

**19 tadan 7 tasi yo'q:** depression, joint_reflection_cracking, lane_shoulder_drop_off, railroad_crossing, shoving, slippage_cracking, swell.

**Disbalans jiddiy:** eng katta klass (250) eng kichigidan (2) **125 barobar** katta. Bleeding va corrugation'ni bu holicha o'rgatib bo'lmaydi.

---

## 5. ⚠️ Yorliq sifati — ehtiyot bo'lish kerak

Ikki mustaqil tekshiruv o'tkazdim.

### 5.1 RDD annotatsiyalari bilan kesishtirish

863 ta RDD-dan olingan rasmning 758 tasi RDD2018 annotatsiyalarida mavjud. QOPLAMA ning ASTM yorlig'ini RDD ning o'z bbox kodlari bilan solishtirdim:

| QOPLAMA yorlig'i | Eng ko'p uchragan RDD kodi | Kutilgan kod |
|---|---|---|
| alligator_cracking (92) | **D00**: 28 ta | D20 |
| bumps_and_sags (93) | **D20**: 44 ta | — |
| edge_cracking (107) | **D20**: 27 ta | — |
| rutting (14) | **D44** (chiziq bo'yog'i): 6 ta | D40 |
| weathering_raveling (107) | **D43** (piyoda o'tish bo'yog'i): 17 ta | — |
| potholes (38) | D20: 10, **D40: atigi 7** | D40 |

`alligator_cracking` deb belgilangan rasmlarning ko'pchiligida RDD **D20 (alligator) emas, D00 (bo'ylama yoriq)** bor. `rutting` rasmlarida esa asosan **oq chiziq bo'yog'i** annotatsiyasi.

**Adolatli bo'lish uchun:** RDD annotatsiyalari ham to'liq emas — bitta rasmda bir nechta nuqson bo'lishi va RDD faqat bittasini belgilagan bo'lishi mumkin. Shuning uchun mos kelmaslik **avtomatik ravishda xato degani emas**. Lekin `rutting → oq chiziq` kabi naqshlar tasodifiy emas.

### 5.2 Vizual tekshiruv

5 ta Toshkent rasmini ochib ko'rdim, **2 tasida aniq xato**:
- `Potholes/IMG_20260711_080604.jpg` → aslida **quduq atrofidagi yamoq** (ASTM #11 Patching), chuqurcha emas
- `Rutting/IMG_20260728_074225.jpg` → aslida **bo'ylama yoriq / qurilish choki**, g'ildirak izi emas

`Polished Aggregate` namunasi esa to'g'ri ko'rindi.

### 5.3 Xulosa

| Qism | Ishonch | Qanday ishlatamiz |
|---|---|---|
| 278 Toshkent rasmi | **O'rta** | Qayta ko'rikdan keyin — validatsiya + demo + fine-tuning |
| 863 RDD-dan qayta yorliqlangan | **Past** | O'qitish uchun to'g'ridan-to'g'ri ishlatmaymiz |

**Tavsiya:** 278 ta Toshkent rasmini bitta odam (yaxshisi yo'l muhandisi) qayta ko'rib chiqsin — bu ~2 soatlik ish va datasetning qiymatini keskin oshiradi. 863 ta yapon rasmini qayta yorliqlashga vaqt sarflash shart emas — bizda RDD2022 ning 47 ming annotatsiyalangan rasmi bor.

---

## 6. Yana bir cheklov: bu **classification**, **detection** emas

Papka = yorliq. Bounding box ham, maska ham yo'q.

PCI uchun bizga **miqdor** kerak (m², m, dona). Rasm darajasidagi "bu rasmda alligator bor" yorlig'idan miqdor chiqmaydi.

Demak QOPLAMA:
- ✅ ASTM klass taksonomiyasini beradi
- ✅ In-domain Toshkent rasmlarini beradi
- ❌ Detektor o'qitish uchun yetarli emas
- ❌ Miqdor o'lchash uchun yetarli emas

Detektsiya va segmentatsiya signali **RDD2022** va **Attain** dan keladi.

---

## 7. Xulosa: QOPLAMA nima uchun kerak

1. **ASTM taksonomiyasi** — loyihaning umumiy klass tizimi shu asosda quriladi
2. **278 ta Toshkent rasmi** — yagona in-domain ma'lumotimiz. Validatsiya to'plami va demo uchun.
3. **Yuqori aniqlik (4000×3000)** — yorilish kengligini mm da o'lchash tajribalari uchun
4. **GPS** — xaritali PCI qatlamini ko'rsatish uchun

Bu **poydevor emas, yo'naltiruvchi**. Poydevor — RDD2022 + Attain.

**Keyingi qadam:** Toshkentda ko'proq rasm yig'ish kerak. 278 emas, 2000+. Iloji bo'lsa mashina oynasiga o'rnatilgan telefon bilan, video rejimida — shunda RDD/Attain bilan bir xil rakurs bo'ladi va GPS trek ham chiqadi.
