# SMART ROAD — ASTM D6433 asosida asfalt sifatini baholovchi model
### Loyiha tushuntirishi va reja · National Transport Hackathon 2026

---

## 0. Birinchi navbatda: vaqt hisobi

Siz "3 hafta" dedingiz, lekin **bugun 25-iyul, hakaton 6-avgust — bu 12 kun**. Reja shunga moslashtirildi. Bu yetarli, lekin "hammasini qilamiz" emas, "to'g'ri narsani qilamiz" degani.

---

## 1. ASTM D6433 nima? (PDF'ni to'liq o'qib chiqdim)

Bu standart **PCI (Pavement Condition Index)** — yo'l qoplamasining 0–100 oralig'idagi bahosini vizual ko'zdan kechirish orqali aniqlash tartibini belgilaydi. AQSh Armiya Muhandislari korpusi ishlab chiqqan, DOD va APWA qabul qilgan.

### 1.1 Baholash shkalasi (Fig. 1)

| PCI | Reyting |
|---|---|
| 85–100 | Good (Yaxshi) |
| 70–85 | Satisfactory (Qoniqarli) |
| 55–70 | Fair (O'rtacha) |
| 40–55 | Poor (Yomon) |
| 25–40 | Very Poor (Juda yomon) |
| 10–25 | Serious (Jiddiy) |
| 0–10 | Failed (Yaroqsiz) |

### 1.2 Algoritm — bu eng muhim qism

Yo'l **branch → section → sample unit** ga bo'linadi. Asfalt (AC) uchun bitta **sample unit = 225 ± 90 m²** (2500 ± 1000 ft²).

Har bir sample unit uchun:

**1-qadam.** 19 ta asfalt buzilish turining har biri uchun, 3 ta jiddiylik darajasida (**L / M / H**), miqdorni o'lchash. O'lchov birligi turga qarab farq qiladi:
- **m²** (maydon): alligator cracking, bleeding, block cracking, corrugation, depression, patching, polished aggregate, railroad crossing, rutting, shoving, slippage cracking, swell, weathering/raveling
- **m** (uzunlik): bumps & sags, edge cracking, joint reflection cracking, lane/shoulder drop-off, longitudinal & transverse cracking
- **dona** (son): potholes

**2-qadam.** Zichlik:
```
Density(%) = (miqdor / sample_unit_maydoni) × 100
```

**3-qadam.** Har bir (tur, jiddiylik, zichlik) uchun **Deduct Value (DV)** — Appendix X3 dagi egri chiziqlardan (X3.1 – X3.25). Bular logarifmik shkalada.

**4-qadam.** Ruxsat etilgan deduct'lar soni:
```
m = 1 + (9/98) × (100 − HDV),   m ≤ 10
```
HDV = eng katta individual deduct value. DV'larni kamayish tartibida saralab, faqat eng katta `m` tasini olamiz (kasr qismi ham — masalan m=7.9 bo'lsa, 8-chi DV ning 0.9 qismi).

**5-qadam — iterativ CDV.** Bu eng nozik joyi:
- `q` = 2.0 dan katta DV'lar soni
- TDV = DV'lar yig'indisi
- (TDV, q) → **CDV** (Fig. X3.26 egri chizig'idan)
- Eng kichik 2.0 dan katta DV ni 2.0 ga tushirib, qaytaramiz — to q=1 bo'lguncha
- **max CDV** = barcha iteratsiyalardagi eng kattasi

**6-qadam.**
```
PCI = 100 − max CDV
```

**Section PCI** = sample unit'larning maydonga vaznlangan o'rtachasi (Eq. 5).

### 1.3 Standartdagi rasmiy misol (Fig. 4 → Fig. 6)

Springfield, sample unit 1, 2500 ft². Kirish: alligator L=13, alligator H=14, edge L=130, joint refl. M=143, patching H=22, pothole L=1, rutting L=21, weathering L=250.
→ HDV = 25.1, m = 7.9, **max CDV = 51, PCI = 49 (Fair)**

**Bu bizning PCI dvigatelimiz uchun test-keys bo'ladi.** Agar kodimiz shu kirishdan 49 chiqarsa — dvigatel to'g'ri.

---

## 2. Loyiha aslida nima bo'ladi

**Bir jumlada:** telefon/dashcam video → har bir kadrda buzilishlarni aniqlash va segmentatsiya → real dunyo o'lchovlariga (m², m) o'tkazish → jiddiylikni aniqlash → ASTM D6433 matematikasi → yo'lning har 200 metriga PCI bahosi → xaritada rangli qatlam.

**Nima uchun bu kuchli g'oya:**
- Vazirlik uchun **aniq, xalqaro standartga asoslangan raqam** beradi — "yo'l yomon" emas, "PCI = 47, Poor, ta'mir kerak"
- PCI to'g'ridan-to'g'ri **byudjet rejalashtirishga** ulanadi — qaysi ko'chani birinchi ta'mirlash kerakligini raqam hal qiladi
- Hozir bu ish O'zbekistonda qo'lda, inspektor bilan, ruletka bilan qilinadi

### 2.1 Siz bergan ArcGIS notebook — nima qilgan va nima qilmagan

Tekshirdim. U **aynan sizdagi datasetni** ishlatgan (9,053 rasm), SSD + ResNet101, 30 epoch. Natijalari:

| Klass | AP |
|---|---|
| D43 (white line blur) | 0.814 |
| D20 (alligator) | 0.762 |
| D01 | 0.730 |
| D44 (crosswalk blur) | 0.649 |
| D00 | 0.559 |
| D10 | 0.258 |
| D40 (pothole/rutting) | 0.170 |
| D11 | 0.144 |
| D30 | 0.000 |

**Muhim:** u faqat detektsiyalarni **sanaydi** va xaritaga qo'yadi. **Hech qanday indeks hisoblamaydi.** Ya'ni bizning PCI qismi — bu bizning farqimiz. Va 2018-yilgi SSD arxitekturasini bugungi modellar bilan osongina yengamiz.

---

## 3. Sizdagi dataset — reallik tekshiruvi

`RoadDamageDataset/` ni to'liq tahlil qildim:

| Ko'rsatkich | Qiymat |
|---|---|
| Rasmlar (JPEG) | 9,892 |
| Annotatsiyali rasmlar | 9,053 |
| Bounding box'lar | 15,457 |
| O'lcham | hammasi 600×600 |
| Format | Pascal VOC XML + YOLO txt |
| Hajm | 1.8 GB |

**Klasslar taqsimoti:**

| Klass | Ma'nosi | Soni | ASTM D6433 ga mos keladimi? |
|---|---|---|---|
| D01 | Uzunasiga yoriq, qurilish choki | 3,789 | ✅ #10 Long & Trans Cracking |
| **D44** | **Piyoda o'tish joyi bo'yog'i o'chgan** | **3,733** | ❌ **PCI da yo'q** |
| D00 | Uzunasiga yoriq, g'ildirak izi | 2,768 | ✅ #10 |
| D20 | Alligator (charchoq) yorig'i | 2,541 | ✅ #1 Alligator Cracking |
| **D43** | **Yo'l chizig'i o'chgan** | **817** | ❌ **PCI da yo'q** |
| D10 | Ko'ndalang yoriq | 742 | ✅ #10 |
| D11 | Ko'ndalang yoriq, chok | 636 | ✅ #10 |
| D40 | Chuqurlik / rutting / ajralish | 409 | ✅ #13 Potholes / #15 Rutting |
| D30 | (noaniq) | 22 | ❌ tashlab yuboriladi |

### 3.1 Achchiq haqiqat — 3 ta jiddiy kamchilik

**Kamchilik 1 — Jiddiylik (L/M/H) yo'q.**
PCI uchun jiddiylik **majburiy**. RDD datasetida u umuman yo'q. Bu eng katta muammo.

**Kamchilik 2 — O'lchov yo'q.**
Bizda faqat piksel bounding box'lar. PCI m² va m talab qiladi. Bounding box maydoni ≠ buzilish maydoni, va piksel ≠ metr.

**Kamchilik 3 — Buzilish turlari yetarli emas.**
19 ta ASTM turidan RDD faqat **4 tasini** qoplaydi. Yo'q: patching (juda keng tarqalgan!), weathering/raveling, block cracking, edge cracking, bleeding, lane/shoulder drop-off.

**Va yana:** box'larning **29%** (D43+D44) — yo'l bo'yoqlari, PCI ga umuman aloqasi yo'q.

Ya'ni: **hozirgi dataset bilan yolg'iz PCI hisoblab bo'lmaydi.** Lekin buni hal qildim — quyida.

---

## 4. Uchta kamchilikning yechimi (research natijasi)

### 4.1 ✅ Jiddiylik muammosi — **Attain datasetni topdim**

Bu loyihaning eng muhim topilmasi.

**Attain** (Data in Brief, 2025, Amirkabir Univ., Tehron):
- **2,293 rasm**, **19,761 annotatsiya**
- **Har bir annotatsiyada jiddiylik bor: low / medium / high** — pavement engineer'lar qo'lda belgilagan
- **10 ta klass**, bizga kerakligi aynan:

| Attain klassi | Soni | ASTM D6433 |
|---|---|---|
| Linear Crack | 9,019 | #10 Long & Trans |
| Alligator Crack | 4,251 | #1 Alligator |
| Weathering | 2,361 | #19 Weathering/Raveling |
| Faded Marking | 1,457 | (PCI da yo'q) |
| **Patching** | 875 | **#11 Patching** |
| Pothole | 525 | #13 Potholes |
| Manhole | 504 | (PCI da yo'q) |
| **Lane/Shoulder Drop-off** | 348 | **#9 Lane/Shoulder Drop-Off** |
| Raveling | 360 | #19 |
| **Block Crack** | 61 | **#3 Block Cracking** |

- **Litsenziya: CC BY 4.0** (erkin ishlatiladi, faqat iqtibos)
- **Suratga olish: vindshildga o'rnatilgan smartfon, 20–70 km/soat** — ya'ni **aynan RDD bilan bir xil rakurs**, transfer qiladi
- Formatlar: Polygon, YOLO, Pascal VOC (uchta versiya)
- Yuklab olish: `https://data.mendeley.com/datasets/nykrzdm74f/1`

Bu bir vaqtning o'zida **1-kamchilikni** (jiddiylik) **va 3-kamchilikni** (turlar qamrovi) hal qiladi. Tehron iqlimi va yo'l sifati Toshkentga Yaponiyadan ancha yaqin — bu ham plus.

> ⚠️ Yuklab olgach tekshirish kerak: jiddiylik alohida atribut sifatida saqlanganmi yoki klass nomiga qo'shilganmi (`alligator_high` kabi). Manbadagi jumla biroz chalkash edi.

### 4.2 ✅ O'lchov muammosi — IPM homografiya

Piksel → metrga o'tish uchun **Inverse Perspective Mapping (IPM)**:
- Kamera balandligi (h ≈ 1.2–1.4 m) va pitch burchagi ma'lum deb olinadi
- Yo'l tekis deb faraz qilinadi (flat road assumption)
- Gorizont chizig'i (vanishing point) aniqlanadi
- 4 nuqtali homografiya bilan **bird's-eye view** ga o'tkaziladi — u yerda **1 piksel = doimiy metr**
- Kalibrovka tekshiruvi: **kadrdagi yo'l chizig'i kengligi** (O'zbekistonda qatnov qismi ~3.5 m) referens sifatida

**Cheklov:** aniqlik masofa bilan yomonlashadi. Shuning uchun faqat **kameradan 3–15 m oraliqdagi** zonani hisobga olamiz, undan uzog'ini tashlab yuboramiz. Bu vijdonan to'g'ri yondashuv.

### 4.3 ✅ PCI dvigateli — **tayyor, MIT litsenziyali implementatsiya topdim**

`github.com/brandnewbox/pavement_condition_index` (Ruby, **MIT**).

Ichini ochib ko'rdim — bizga kerak bo'lgan hamma narsa bor:

| Fayl | Nima bor |
|---|---|
| `calculated_deduct_coefficients.rb` | **Barcha 19 asfalt + 19 beton buzilish turi uchun, L/M/H bo'yicha polinom koeffitsientlari** |
| `calculated_corrected_deduct_coefficients.rb` | CDV egri chiziqlari, q1…q10 uchun polinomlar |
| `cdv_iteration.rb` | Iterativ CDV protsedurasi |
| `observed_deduct_values.rb` | Egri chiziqlardan qo'lda o'qilgan xom nuqtalar (o'zimiz qayta fit qilishimiz mumkin) |

**Aniq formula (kodini o'qib chiqdim):**
```
DV(density, tur, jiddiylik):
    d = clamp(density, valid_min, valid_max)
    x = log10(d)              # asfalt uchun (chart_type = :log)
    DV = Σ cᵢ · xⁱ            # polinom
    return clamp(DV, 0, 100)

CDV(TDV, q) = Σ cᵢ · TDVⁱ     # har bir q uchun alohida polinom
```

Masalan alligator cracking: `low = [11.810, 14.717, 5.255]` → `DV = 11.810 + 14.717·log₁₀(d) + 5.255·log₁₀(d)²`

**Eng yaxshisi:** uning test'lari **ASTM ning Fig. 4 rasmiy misolini** tekshiradi va `PCI = 49`, `maxCDV = 51`, `HDV = 25.1`, `m = 7.9` chiqishini talab qiladi. Ya'ni Python'ga ko'chirganimizda **standartning o'z misoli bilan validatsiya qila olamiz**.

Bu 1 kunlik ish. **PCI dvigateli — risk emas, hal qilingan.**

---

## 5. Datasetlar rejasi

### Tier 1 — majburiy (hakatongacha)

| Dataset | Hajm | Nima beradi | Manba |
|---|---|---|---|
| **RDD2022** | 47,420 rasm, 6 davlat | Asosiy detektsiya korpusi. Sizdagi RDD2018 ning kattalashgani | figshare / Kaggle: `aliabdelmenam/rdd-2022` · CC BY-SA 4.0 |
| **Attain** | 2,293 rasm, 19,761 obj | **Jiddiylik (L/M/H) + patching, weathering, block crack** | Mendeley `nykrzdm74f` · CC BY 4.0 |
| **CrackSeg9k** yoki khanhha | ~9–11k mask | **Piksel maskalar** → maydon/uzunlik o'lchash | Kaggle: `lakshaymiddha/crack-segmentation-dataset` |
| Sizdagi RDD2018 | 9,053 | Bazaviy, val uchun | mavjud |

### Tier 2 — vaqt bo'lsa

| Dataset | Nima uchun |
|---|---|
| **SVRDD** (Zenodo, 8,000 rasm, CC BY 4.0) | Ko'cha rakursi, patch va manhole klasslari bor, VOC+YOLO tayyor |
| **Pothole Mix** (Mendeley, 4,340 mask) | Chuqurlik segmentatsiyasi. ⚠️ CC BY-**NC** — tijorat uchun cheklov |
| **Pothole-600** (`rangerfan/pothole-600`) | Stereo disparity → chuqurlik proksi |
| **Mapillary Toshkent** | CC BY-SA, API bepul, Toshkentda qamrov bor — **demo va domain-check uchun** |

### ❌ Ishlatmaymiz
**Google Street View** — ToS AI model o'qitishni **aniq taqiqlaydi**. Davlat loyihasida bu qabul qilinmaydi.

---

## 6. Model tanlovi

### 6.1 ⚠️ Litsenziya — buni hozir hal qilish kerak

**Barcha Ultralytics YOLO (v8…v11, v12) — AGPL-3.0.** AGPL tarmoq bandi bor: agar model server orqali xizmat qilsa, **butun ilova kodini ochiq qilish** shart, aks holda Enterprise litsenziya sotib olinadi.

Bu **Transport vazirligi** loyihasi. Agar keyinchalik yopiq tizimga joylashtirmoqchi bo'lishsa, AGPL to'siq bo'ladi.

**Tavsiyam:** ikki yo'ldan borish
- **Hakaton uchun:** YOLO11/YOLO12 (tooling eng yaxshi, tez natija) — kodni ochiq qilamiz, muammo yo'q
- **Zaxira/deploy uchun:** **D-FINE** yoki **RF-DETR** — ikkalasi ham **Apache-2.0**, aniqligi YOLO bilan teng yoki yaxshiroq

Pitch'da buni aytish o'zi ustunlik: *"biz litsenziya masalasini oldindan hal qildik"*.

### 6.2 CRDDC'2022 chempionlari nima qilgan (benchmark)

RDD2022 bo'yicha rasmiy natijalar:

| O'rin | Jamoa | F1 | Retsept |
|---|---|---|---|
| 1 | ShiYu_SeaView | **0.770** | YOLOv5+v7 **va** Cascade R-CNN+Swin ansambli |
| 2 | DongjunJeong | 0.743 | YOLOv5x P5+P6 ansambl, patching |
| 3 | MDPT | 0.741 | YOLOv7 + coordinate attention |

**Asosiy xulosa:** 1-o'rin bilan 10-o'rin orasidagi farq — arxitektura emas, **ansambl + TTA**. Va ular 2022-yilgi YOLOv5/v7 ishlatgan. Bizda 2026-yilgi modellar bor.

### 6.3 Bizning stack

```
A) DETECTOR      YOLO11-m/l  (+ D-FINE-L ansambl uchun)
                 imgsz 640 baza, 1024 yuqori aniqlik uchun
                 
B) SEGMENTER     YOLO11-seg  (yoki SegFormer, agar vaqt bo'lsa)
                 → maydon (m²) va uzunlik (m) uchun mask
                 
C) SEVERITY      Attain'da o'qitilgan crop klassifikatori (L/M/H)
                 + geometrik yorilish kengligi (skeleton + distance transform)
                 ikkisi birlashtiriladi
                 
D) PCI ENGINE    ASTM D6433 matematikasi (Python port)
                 + IPM homografiya (piksel → metr)
```

---

## 7. Kaggle 2×T4 training rejasi

### 7.1 Muhim texnik ogohlantirish

Kaggle'da **2×T4 DDP osilib qolish muammosi** ma'lum (Ultralytics'da bir necha ochiq issue bor).

**Yechim — DDP'ni umuman ishlatmaymiz:**
```
GPU 0  →  YOLO11-l   (seed 1)     ┐
GPU 1  →  D-FINE-L yoki YOLO11-m  ┘  ikkita mustaqil job
```
Bu bir vaqtda:
- DDP riskini nolga tushiradi
- **Ikkala T4 ham 100% ishlaydi**
- Va tayyor **ansambl** beradi (WBF bilan birlashtiramiz) — bu aynan CRDDC 1-o'rin retsepti

### 7.2 Kaggle cheklovlari va checkpoint strategiyasi

- Haftada **30 GPU-soat**, bitta sessiya maksimum **12 soat**
- `/kaggle/working` ~20 GB
- **T4'da bf16 yo'q** → `amp=True` (fp16)

**Backup strategiyasi (siz aytgan zaxira modeli):**
1. Har 10 epochda `best.pt` ni **Kaggle Dataset** ga saqlash (Save Version)
2. Har sessiya oxirida `last.pt` + `best.pt` → alohida private Kaggle Dataset
3. Keyingi sessiyada uni **input dataset** sifatida ulash, `resume=True`
4. Hakaton oldidan eng yaxshi checkpoint'ni **`smart-road-backup-v1`** deb muzlatib qo'yish

Shunday qilib hakatonda training yomon ketsa — bir click bilan zaxira.

### 7.3 Training parametrlari (boshlang'ich)

```
imgsz=640, batch=16, epochs=100, amp=True
close_mosaic=10
copy_paste=0.3          # kam uchraydigan klasslar uchun (pothole!)
D40/pothole rasmlarni oversample qilish
optimizer=AdamW, lr0=0.001, cos_lr=True
```

**Vaqt hisobi:** ~20k rasm, 640px, YOLO11-m, 1×T4 → taxminan **3–5 min/epoch** → 100 epoch ≈ **6–8 soat**. Ya'ni bitta 12-soatlik sessiyaga sig'adi.

### 7.4 Inference bosqichida aniqlikni oshirish (bepul yutuq)

- **TTA** (horizontal flip + 2–3 masshtab) — `augment=True`
- **WBF** (Weighted Boxes Fusion) — ikkita modelni birlashtirish, NMS'dan yaxshiroq
- **SAHI** (tiled inference) — yuqori aniqlikdagi rasmlar va uzoqdagi ingichka yoriqlar uchun

Research ko'rsatishicha bular birgalikda **+3–6 F1 punkt** beradi.

---

## 8. Kod yozish rejasi — modul-modul

> Bu bosqichda kod yozmayapman (siz aytganingizdek). Bu — yozilganda qanday tuzilishi.

```
smart_road/
├── data/
│   ├── convert_rdd.py          # VOC XML → unified schema
│   ├── convert_attain.py       # Attain → unified schema (severity bilan)
│   ├── unify_taxonomy.py       # ⭐ hamma datasetni bitta klass tizimiga
│   └── splits.py               # train/val/test, shahar bo'yicha stratifikatsiya
│
├── models/
│   ├── train_detector.py       # YOLO11 / D-FINE
│   ├── train_segmenter.py      # YOLO11-seg
│   └── train_severity.py       # crop klassifikatori (L/M/H)
│
├── geometry/
│   ├── ipm.py                  # ⭐ homografiya, piksel → metr
│   ├── calibrate.py            # kamera balandligi, gorizont, lane-width check
│   └── measure.py              # mask → m² / m; skeleton → yorilish kengligi (mm)
│
├── pci/
│   ├── deduct_curves.py        # ⭐ ASTM D6433 polinom koeffitsientlari
│   ├── cdv.py                  # iterativ CDV protsedurasi
│   ├── engine.py               # PCI = 100 − maxCDV
│   ├── mapping.py              # ⭐ model klasslari → ASTM 19 turi
│   └── test_astm_example.py    # ⭐ Fig.4 → PCI = 49 (validatsiya)
│
├── pipeline/
│   ├── video_to_segments.py    # video → 200m yo'l bo'laklari (GPS bilan)
│   └── segment_to_pci.py       # bo'lak → PCI + hisobot
│
└── viz/
    └── map_layer.py            # GeoJSON, PCI rangi bilan
```

### 8.1 Eng muhim modul: `pci/mapping.py`

Model klasslarini ASTM turlariga o'tkazish jadvali:

| Model klassi | ASTM # | Nomi | Birlik |
|---|---|---|---|
| D00, D01, D10, D11 / linear_crack | 10 | Longitudinal & Transverse Cracking | **m** |
| D20 / alligator_crack | 1 | Alligator Cracking | **m²** |
| D40 / pothole | 13 | Potholes | **dona** |
| patching | 11 | Patching & Utility Cut | **m²** |
| weathering, raveling | 19 | Weathering / Raveling | **m²** |
| block_crack | 3 | Block Cracking | **m²** |
| lane_shoulder_dropoff | 9 | Lane/Shoulder Drop-Off | **m** |
| D43, D44, faded_marking, manhole | — | **PCI ga kirmaydi, tashlanadi** | — |

Bu bilan **19 tadan 7 tasini** qoplaymiz.

---

## 9. Kun-ma-kun reja (25-iyul → 6-avgust)

| Kun | Ish |
|---|---|
| **1 (25.07)** | Attain + RDD2022 + CrackSeg9k yuklash. Attain'da jiddiylik qanday saqlanganini tekshirish |
| **2** | `unify_taxonomy.py` — hamma datasetni bitta sxemaga. Bu eng zerikarli, lekin eng muhim ish |
| **3** | **PCI dvigateli** Python'ga port. ASTM Fig.4 testi o'tishi shart (PCI=49) |
| **4–5** | Birinchi baseline: YOLO11-m, RDD2022 4-klass. Kaggle pipeline'ni sozlash, checkpoint→Dataset ishlashini tekshirish |
| **6–7** | To'liq detektor: birlashtirilgan dataset, kengaytirilgan klasslar. GPU0/GPU1 parallel |
| **8** | Severity klassifikatori (Attain) + segmentatsiya modeli |
| **9** | `ipm.py` — homografiya, kalibrovka. Toshkent Mapillary rasmlarida sinash |
| **10** | End-to-end: video → PCI. Birinchi to'liq natija |
| **11** | TTA + WBF + SAHI. Ansambl. Metrikalarni yakunlash |
| **12 (05.08)** | **BACKUP MUZLATISH.** Barcha checkpoint'lar Kaggle Dataset'ga. Demo tayyorlash, sheriklarga topshirish |

**Hakaton (6–8.08):** trening qaytadan boshlanadi, natija yomon bo'lsa → `smart-road-backup-v1`.

---

## 10. Kutilayotgan natijalar (realistik)

| Komponent | Kutilayotgan | Asos |
|---|---|---|
| Detektor, RDD2022 4-klass | **F1 0.72–0.78** (bitta model), **0.78–0.82** (ansambl+TTA) | CRDDC 2022 g'olibi 0.770, biz yangiroq arxitektura ishlatamiz |
| Detektor, sizdagi RDD2018 9-klass | **mAP50 0.55–0.65** | ArcGIS SSD baseline ≈ 0.45 — uni ishonchli yengamiz |
| Yorilish segmentatsiyasi | **IoU 0.65–0.75** | CrackSeg9k/OmniCrack30k benchmarklari |
| Jiddiylik (L/M/H) | **aniqlik 75–85%** | bu inson uchun ham subyektiv |
| **PCI dvigateli** | **matematik aniq** | ASTM Fig.4 testi bilan tasdiqlanadi |
| **End-to-end PCI** | **MAE ≈ 8–15 PCI punkt** | Literaturada eng yaxshisi R²=0.75, MAPE 10.4% |

### ⚠️ Halol bo'lish kerak bo'lgan joy

19 ta ASTM turidan biz **7 tasini** qoplaymiz. Qolganlari:
- **Chuqurlik kerak** (rutting, depression, pothole jiddiyligi) — mono kamera bilan ishonchli o'lchab bo'lmaydi
- **Ride quality kerak** (bumps, corrugation, shoving) — bu IMU/akselerometr ishi, rasm emas
- **Juda nozik** (bleeding, polished aggregate, swell) — hozirgi computer vision uddalay olmaydi

**Muhim mantiq:** qoplanmagan har bir tur faqat **deduct qo'shadi**, ya'ni haqiqiy PCI ni **pasaytiradi**. Demak bizning bahomiz — **yuqori chegara (ceiling)**.

Buni yashirmaslik kerak, aksincha — pitch'da shunday aytish:

> *"ID-PCI = 71 (Satisfactory). 19 ta ASTM buzilish turidan kamera orqali kuzatiladigan 7 tasi bo'yicha hisoblangan. Chuqurlikka bog'liq va ride-quality turlari qamrab olinmagan — ular hisobga olinsa baho faqat pasayadi. Ya'ni bu — konservativ yuqori chegara."*

Bu **kuchsizlik emas, muhandislik yetukligi**. Hakim komissiya buni qadrlaydi. Standartni bilmagan jamoa "PCI = 71" deb aytadi va savol berilganda qulaydi; biz nima uchun 71 ekanini va nimani hisoblamaganimizni bilamiz.

---

## 11. Risklar va zaxira rejalari

| Risk | Ehtimol | Zaxira |
|---|---|---|
| Attain'da jiddiylik kutilganidek saqlanmagan | O'rta | O'zimiz 500–1000 crop'ni qo'lda belgilaymiz (2 kun) |
| RDD2022 yuklab olish og'ir (bir necha GB) | Past | Kaggle mirror'dan to'g'ridan-to'g'ri ulanadi, yuklamaymiz |
| Kaggle 2×T4 DDP osiladi | **Yuqori** | DDP ishlatmaymiz — 2 ta mustaqil job (yuqorida) |
| 30 soat/hafta kvota tugaydi | O'rta | Ikkinchi Kaggle akkaunt, yoki Colab zaxira |
| IPM kalibrovkasi noto'g'ri → m² xato | O'rta | Lane-width sanity check; 3–15 m zonaga cheklash |
| Hakatonda internet yo'q / sekin | O'rta | **Hammasini oldindan yuklab, offline olib borish** |

---

## 12. Keyingi qadam

Men hozir kod yozmadim — siz aytganingizdek, datasetlar hali qo'shiladi.

**Sizdan kerak bo'lgan qaror:**
1. Attain datasetni yuklaymizmi? (menimcha — ha, bu loyihaning kaliti)
2. Litsenziya: YOLO (AGPL) yoki D-FINE/RF-DETR (Apache) — yoki ikkalasi?
3. Boshlaymizmi — `unify_taxonomy.py` va PCI dvigatelidan?

---

### Manbalar

- ASTM D6433-07 (loyiha papkasida)
- [brandnewbox/pavement_condition_index](https://github.com/brandnewbox/pavement_condition_index) — MIT, PCI dvigateli
- [Attain dataset](https://data.mendeley.com/datasets/nykrzdm74f/1) — CC BY 4.0, jiddiylik bilan
- [RDD2022 (figshare)](https://figshare.com/articles/dataset/RDD2022_-_The_multi-national_Road_Damage_Dataset_released_through_CRDDC_2022/21431547) · [sekilab/RoadDamageDetector](https://github.com/sekilab/RoadDamageDetector)
- [CRDDC'2022 natijalari](https://arxiv.org/abs/2211.11362) · [RDD2022 maqolasi](https://arxiv.org/abs/2209.08538)
- [Automated PCI Assessment, Sensors 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11014408/) — YOLOv8 → PCI pipeline
- [ArcGIS road surface notebook](https://developers.arcgis.com/python/latest/samples/automate-road-surface-investigation-using-deep-learning/)
- [D-FINE](https://github.com/Peterande/D-FINE) · [RF-DETR](https://github.com/roboflow/rf-detr) — Apache-2.0 alternativalar
- [SAHI](https://github.com/obss/sahi) · [WBF](https://github.com/ZFTurbo/Weighted-Boxes-Fusion)
