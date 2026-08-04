# Train natijalari — vast.ai, 2026-08-02 … 08-04

Instans (RTX 5090, Vengriya) **4-avgust ~06:40 da o'chirildi**. Bu hujjat undan
olingan hamma narsaning yozuvi. Xom artefaktlar: `runs_archive/`.

Ikkala train ham `returncode=0` bilan tugadi, ikkalasi ham **early stopping**
(`patience=30`) bilan to'xtadi — 150 epoch to'liq ishlamadi.

---

## 1. Yakuniy natija

| | **yolo11l @ 640** | yolo11m @ 1024 |
|---|---:|---:|
| Eng yaxshi epoch | **113** | 31 |
| Ishlagan epoch | 143 / 150 | 61 / 150 |
| Davomiylik | 17.8 soat | 16.5 soat |
| Batch | 32 | 24 |
| Parametr | 25.3 M | 20.0 M |
| **mAP50** | **0.657** | 0.544 |
| **mAP50-95** | **0.401** | 0.316 |
| Precision | 0.682 | 0.584 |
| Recall | 0.604 | 0.530 |
| Inference | 2.2 ms/rasm | 5.7 ms/rasm |

➜ **`yolo11l_640` g'olib.** Har bir o'lchovda ustun, ustiga 2.6× tez.
Zaxira model: `models/yolo11l_640_best.pt` (51.2 MB, md5 `51bf3598…`).

⚠️ **Bashorat amalga oshmadi.** `close_mosaic=10` odatda oxirgi epochlarda
mAP ni +0.02…0.04 ga ko'taradi va shunga asosan ~0.67–0.68 kutilgan edi.
Amalda mosaic o'chgach mAP50 **0.655 → 0.653** bo'ldi — o'sish yo'q.
Faqat `cls_loss` tushdi (0.929 → 0.678), ya'ni model train taqsimotiga
moslashdi, val da esa foyda bermadi. **Haqiqiy natija 0.657.**

⚠️ 1024 solishtiruvi to'liq halol emas: u epoch 31 da eng yaxshi natijaga
yetib, 61 da to'xtagan — ya'ni kamroq o'qigan. Lekin 16.5 soat sarflab
0.316 berdi, 640 esa 17.8 soatda 0.401. Bir xil byudjetda 640 yaxshiroq.

---

## 2. Sinf bo'yicha (yolo11l_640, best.pt)

| # | Sinf | val rasm | val box | P | R | mAP50 | mAP50-95 |
|---|---|---:|---:|---:|---:|---:|---:|
| 0 | longitudinal_transverse_crack | 2274 | 4970 | 0.653 | 0.615 | 0.637 | 0.364 |
| 1 | alligator_crack | 1038 | 1533 | 0.653 | 0.652 | 0.672 | 0.388 |
| 2 | **block_crack** | **2** | **2** | 0.608 | 0.500 | 0.502 | 0.502 |
| 3 | patching | 362 | 823 | 0.756 | 0.728 | **0.783** | **0.564** |
| 4 | **pothole** | 456 | 792 | 0.618 | 0.506 | 0.549 | **0.248** |
| 5 | weathering_raveling | 28 | 175 | 0.791 | 0.503 | 0.602 | 0.325 |
| 6 | lane_shoulder_drop_off | **4** | 38 | 0.633 | 0.579 | 0.731 | 0.319 |
| 7 | marking_manhole | 874 | 1346 | 0.741 | 0.752 | 0.781 | 0.501 |

### Bu jadvaldan chiqadigan uchta xulosa

**a) `block_crack` raqami — shovqin, natija emas.**
Butun val to'plamida **2 ta box**. mAP50-95 = 0.502 bu ikki qutidan hisoblangan,
statistik ma'nosi yo'q. `BLOCK_CRACK_GAP.md` dagi muammo raqam bilan tasdiqlandi:
train'da ham atigi **59 ta box**. Professorning ko'chasida esa block cracking —
umumiy CDL ning 46 %. **Model uning asosiy nuqsonini ko'rmaydi.**
Xuddi shu narsa `lane_shoulder_drop_off` ga tegishli (4 val rasm).

**b) `pothole` — PCI uchun eng og'riqli zaif joy.**
mAP50-95 = 0.248, hamma sinf ichida eng past. Ahamiyati oddiy detektsiyadan
kattaroq: ASTM deduct egri chiziqlarida chuqurcha **eng tik** egri chiziqqa ega —
1 % zichlikdagi yuqori darajali chuqurcha o'nlab PCI punktini yeydi
(`YANGIZAMON_PCI.md` dagi S7 misoli aynan shu). Ya'ni bu sinfdagi xato
boshqa sinflardagi xatodan ko'ra ko'proq PCI xatosiga aylanadi.

**c) Yaxshi ishlaydigani — `patching` va `marking_manhole`.**
Ikkalasi ham katta, kontrastli, aniq chegarali obyektlar. Kutilgan.

---

## 3. ⚠️ Sinf soni nomuvofiqligi — buni bilib turish shart

Train'da ishlatilgan `data.yaml` (`runs_archive/data_yaml_used.yaml`):

```yaml
nc: 10
names: {0..7: bizning 8 sinf, 8: edge_crack, 9: bumps_and_sags}
```

Lokal `smartroad/data/build_yolo.py` da esa `CLASSES` — **8 ta**.

Tekshirilgan holat:
- 0–7 indekslar va nomlar **ikkala tomonda aynan bir xil tartibda** ✅
- 8 va 9 sinflar uchun train'da ham, val'da ham **0 ta box** ✅

➜ **Bashoratlar to'g'ri, indeks siljishi yo'q.** Lekin checkpoint'ning
detection head'i **10 chiqishli**, ulardan 2 tasi hech qachon o'qitilmagan.

Amaliy oqibatlari:
1. `model.names` yuklanganda **10 ta** nom qaytaradi, 8 ta emas.
2. `assert len(CLASSES) == model.nc` turidagi tekshiruv **yiqiladi**.
3. O'qitilmagan 8/9 head'lari past ishonchli soxta detektsiya berishi mumkin —
   inference'da `classes=[0,1,2,3,4,5,6,7]` bilan cheklab qo'yish kerak.

Fine-tune qilishdan oldin hal qilinsin: yo `data.yaml` ni 8 ga keltirib
head qayta quriladi, yo 10 sinf saqlanib, 8/9 doimiy filtrlanadi.

---

## 4. Dataset (aynan train ko'rgan holat)

`runs_archive/class_histogram.json` — bevosita train diskidan sanalgan.

| # | Sinf | train box | val box |
|---|---|---:|---:|
| 0 | longitudinal_transverse_crack | 53 293 | 4 971 |
| 1 | alligator_crack | 16 056 | 1 533 |
| 2 | block_crack | **59** | **2** |
| 3 | patching | 7 719 | 823 |
| 4 | pothole | 7 394 | 792 |
| 5 | weathering_raveling | 1 805 | 175 |
| 6 | lane_shoulder_drop_off | 308 | 38 |
| 7 | marking_manhole | 17 334 | 1 346 |
| | **Jami** | **103 968** | **9 680** |

Rasm: **40 994 train + 3 550 val** = 44 544. Bo'sh yorliq fayli **yo'q**.
Bu raqamlar `HANDOFF.md` dagi qiymatlar bilan to'liq mos ✅

Sinf muvozanatsizligi 0-sinf : 2-sinf = **903 : 1**.

---

## 5. Giperparametrlar (`runs_archive/yolo11l_640/args.yaml`)

```
model=yolo11l.pt   imgsz=640   batch=32   epochs=150   patience=30
optimizer=AdamW    lr0=0.001   lrf=0.01   cos_lr=true  warmup_epochs=3
amp=true           seed=1337   deterministic=true      workers=12
mosaic=1.0  close_mosaic=10  mixup=0.1  copy_paste=0.3 (flip)  erasing=0.4
hsv_h=0.015  hsv_s=0.7  hsv_v=0.4  translate=0.1  scale=0.5  fliplr=0.5
degrees=0.0  flipud=0.0  rect=false  multi_scale=false
```

Muhit: Ultralytics 8.3.155, torch 2.12.0+cu130, Python 3.12.13, RTX 5090 32 GB.

`seed=1337` + `deterministic=true` — natija takrorlanadigan.

---

## 6. Arxivda nima bor

```
runs_archive/
  yolo11l_640/            ⭐ asosiy run
    weights/best.pt       md5 51bf35981aa587ff12c202f119de5f14  (epoch 113)
    weights/last.pt       md5 ec806108bbbb26ed159e7bd2fee73ee5  (epoch 143)
    results.csv           143 qator, har epoch metrikasi
    args.yaml             to'liq giperparametrlar
    *.png                 PR/P/R/F1 egri chiziqlari, confusion matrix, results
    train_batch*.jpg  val_batch*_{labels,pred}.jpg
    labels.jpg  labels_correlogram.jpg
  yolo11m_1024/           xuddi shu tuzilma, 61 qator
  yolo11l_640.log.gz      3.0 MB (siqilmagan 50 MB)
  yolo11m_1024.log.gz     1.5 MB (siqilmagan 30 MB)
  train.py                instansda ishlagan skript
  data_yaml_used.yaml     ⚠️ nc:10 — 3-bo'limga qara
  class_histogram.json    4-bo'lim raqamlari
  orchestrator.log  setup.log  train_results.json
```

`models/` dagi zaxira nusxalar (hammasi md5 bo'yicha tekshirilgan):

| Fayl | md5 | Nima |
|---|---|---|
| `yolo11l_640_best.pt` | `51bf3598…` | ⭐ **zaxira model** |
| `yolo11l_640_last.pt` | `ec806108…` | fine-tune uchun |
| `yolo11m_1024_best.pt` | `d5d97021…` | eski run |
| `yolo11m_1024_last.pt` | `2c89a2bb…` | eski run |

Ko'chirishdan keyin lokal va masofaviy md5 **bittama-bitta solishtirilgan**,
hammasi mos keldi. Instansdan olinmagan yagona narsa — `/workspace/data`
(4.7 GB dataset), u `DATA/manifests/` dan `build_yolo.py` bilan qayta quriladi,
va yuklab olingan bazaviy vaznlar (`yolo11{n,m,l}.pt`, ochiq).

---

## 7. Keyingi qadamlar uchun xulosa

1. **Fine-tune bazasi tayyor** — `yolo11l_640_best.pt`. 0 dan train qilish
   kerak emas.
2. **`nc` masalasi fine-tune'gacha hal qilinsin** (3-bo'lim).
3. **block_crack — 1-raqamli bo'shliq.** `LABEL_TASK/` paketi shu uchun
   tayyorlangan. 160 ta yangi parcha 59 ta mavjud box ustiga qo'shilsa,
   bu ~3.7× o'sish. Professor seansi shuning uchun kerak.
4. **pothole aniqligini oshirish PCI ga eng katta ta'sir beradi** — SAHI
   (tiled inference) shu yerda ham foyda berishi mumkin.
5. **`patience=30` juda qisqa bo'lgan.** 640 run epoch 113 da eng yaxshi
   natijaga yetdi, ya'ni 100-epochdan keyin ham o'sish bor edi. Keyingi
   safar `patience=50…60` yoki `patience=0`.
