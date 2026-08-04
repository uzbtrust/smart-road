# Yorliqlash vazifasi — yoriq turlarini bboxlash

**Vaqt:** ~2 soat · **Rasm:** 160 ta parcha · **Joy:** `LABEL_TASK/block_crack/`

---

## Nega bu kerak

Butun datasetimizda block cracking uchun **61 ta box** bor. Professorning Yangizamon
tadqiqotida esa block cracking — **eng ko'p uchraydigan nuqson, umumiy CDL ning 46 %**,
12 bo'lakning 7 tasida yetakchi nuqson. Model uni ko'rmasa, validatsiya barbod bo'ladi.

## Nega to'g'ridan-to'g'ri QOPLAMA rasmlariga emas

Ikki sabab:

1. **O'lcham.** QOPLAMA rasmlari 4000×3000. Model kirishi 640–1024 px. Ya'ni 4–6 barobar
   siqiladi va ingichka yoriq naqshi butunlay yo'qoladi. Shuning uchun men rasmlarni
   **1400×1400 parchalarga** bo'lib, 1024 ga keltirdim — siqilish atigi 1.4 barobar,
   naqsh saqlanadi va videodagi yaqin maydon masshtabiga mos keladi.

2. **Papka nomi ishonchsiz.** "Block Cracking" papkasidagi rasmlarning ko'pi aslida
   bitta uzun yoriq, ya'ni bo'ylama/ko'ndalang. Shuning uchun **papka nomiga qaramang** —
   har bir boxning turini o'zingiz ko'rib hal qilasiz.

160 parcha "yoriqqa o'xshash tarkib" bo'yicha avtomatik saralangan — bo'sh asfaltga
vaqt sarflamaysiz. Ular hamma yoriq papkalaridan olingan, faqat block cracking'dan emas.

---

## 1. Dastur

**makesense.ai** — brauzerda ishlaydi, o'rnatish shart emas, rasmlar internetga
yuklanmaydi (hammasi kompyuterda bajariladi).

1. https://www.makesense.ai → **Get Started**
2. `LABEL_TASK/block_crack/images/` ichidagi **160 rasmni** sudrab tashlang
3. **Object Detection** ni tanlang
4. Sinf ro'yxatini `LABEL_TASK/block_crack/classes.txt` faylidan yuklang
   (**Load labels from file** tugmasi) — tartib muhim, o'zgartirmang
5. Ishni boshlang

Muqobil (to'liq oflayn): `pip install labelImg` → `labelImg images classes.txt`.
Formatni **YOLO** ga o'zgartirishni unutmang.

---

## 2. Sinflar va ularni farqlash

Faqat shu **beshtasi** kerak. Qolganlarini (`lane_shoulder_drop_off`, `marking_manhole`)
bu vazifada qo'ymaymiz.

### Asosiy savol ketma-ketligi

```
Yoriqlar bir-biriga ulanib YOPIQ SHAKL hosil qilyaptimi?
├── YO'Q  →  longitudinal_transverse_crack   (bitta chiziq, tarmoqlanmagan)
└── HA
     ├── shakllar KATTA, to'rtburchakka o'xshash (30 sm – 3 m)  →  block_crack
     └── shakllar KICHIK, burchakli, notekis (< 50 sm)          →  alligator_crack
```

### `block_crack` (ASTM №3) — bloksimon yoriq

- Asfaltni **taxminan to'rtburchak bo'laklarga** bo'ladi, panjaraga o'xshaydi
- Bo'lak o'lchami **0.1 m² dan 9 m² gacha** — ya'ni tomoni ~30 sm dan ~3 m gacha
- Sababi **asfaltning qurishi va harorat**, transport emas
- Shuning uchun **yo'lning hamma joyida** bo'ladi, g'ildirak izida ham, chetida ham
- Chiziqlari nisbatan **to'g'ri**

### `alligator_crack` (ASTM №1) — to'rsimon yoriq

- Ko'p burchakli, **o'tkir burchakli mayda bo'laklar**, tovuq to'riga o'xshaydi
- Bo'lak eng uzun tomoni odatda **50 sm dan kichik**
- Sababi **takroriy transport yuki (charchoq)**
- Shuning uchun **faqat g'ildirak izida** bo'ladi, yo'l chetida bo'lmaydi
- Ko'pincha ikkita parallel bo'ylama yoriqdan boshlanib, keyin to'rga aylanadi

> **Eng oson farq:** bo'lak katta va to'rtburchak → block. Bo'lak mayda va notekis,
> g'ildirak izida → alligator.

### `longitudinal_transverse_crack` (ASTM №10) — bo'ylama va ko'ndalang yoriq

- **Bitta chiziq**, yopiq shakl hosil qilmaydi
- Yo'l o'qiga parallel (bo'ylama) yoki tik (ko'ndalang)
- Kichik tarmoqlari bo'lishi mumkin, lekin **yopiq to'rtburchak hosil qilmaydi**

### `patching` (ASTM №11) — yamoq

- Asl qoplamadan **rangi/teksturasi boshqacha** to'rtburchak yoki notekis maydon
- Chetlari aniq ko'rinadi

### `pothole` (ASTM №13) — chuqurcha

- Qoplamadagi **teshik**, chetlari o'tkir, ichi qorong'i
- Faqat haqiqiy teshik. Shunchaki qora dog' emas

---

## 3. Box qanday chiziladi

Bu **eng muhim qism** — noto'g'ri chizilgan box modelni buzadi.

### Maydon nuqsonlari — `block_crack`, `alligator_crack`, `patching`

ASTM bularni **m² da** o'lchaydi. Shuning uchun:

> **Butun zararlangan maydon atrofiga BITTA box** chizing.
> Har bir yoriq chizig'iga alohida box **chizmang**.

Box naqsh boshlangan joydan tugagan joyigacha bo'lsin, ortiqcha toza asfalt qo'shmang.

### Chiziqli nuqson — `longitudinal_transverse_crack`

ASTM buni **metrda** o'lchaydi. Shuning uchun:

> **Har bir alohida yoriqqa alohida box**, yoriq bo'ylab tor qilib.

Ikkita yoriq kesishsa — ikkita box. Box yoriqdan 5–10 px kengroq bo'lsa yetadi.

### Umumiy qoidalar

| Qoida | Sabab |
|---|---|
| Faqat **yo'l qoplamasi** — trotuar, bordyur, o't emas | PCI faqat qoplama uchun |
| Bitta piksel ustiga **ikkita sinf qo'ymang** | zichlik ikki marta sanaladi |
| Soyada aniq ko'rinmasa — **tashlab keting** | noto'g'ri yorliq yo'qdan yomonroq |
| Ishonchingiz komil bo'lmasa — **qo'ymang** | 100 ta toza yorliq 200 ta shubhalidan yaxshi |
| Bo'sh parcha bo'lsa — box qo'ymay keyingisiga o'ting | bo'sh rasm ham foydali (negative) |

### Masshtabni qanday chamalash

Parchalarda o'lchov uchun:
- **yo'l chizig'i kengligi ≈ 10–15 sm** (ko'rinsa, eng ishonchli o'lchagich)
- **asfalt toshchalari ≈ 1–2 sm**

30 sm ≈ ikki-uch barobar chiziq kengligi. Shundan block/alligator farqini chamalang.

---

## 4. Natijani saqlash

**makesense.ai:** Actions → **Export Annotations** → **A .zip package containing
files in YOLO format** → arxivni oching → `.txt` fayllarni
`LABEL_TASK/block_crack/labels/` ichiga qo'ying.

**labelImg:** allaqachon `labels/` ga yozadi.

Har bir `.txt` fayl nomi rasm nomi bilan bir xil bo'lishi kerak:
`t000_IMG_20260711_080954_2000_900.jpg` → `t000_IMG_20260711_080954_2000_900.txt`

Fayl ichidagi format (YOLO, normallashtirilgan 0–1):
```
<sinf_raqami> <markaz_x> <markaz_y> <kenglik> <balandlik>
2 0.512340 0.634210 0.284000 0.192000
0 0.223000 0.410000 0.061000 0.338000
```

Sinf raqamlari:
```
0 longitudinal_transverse_crack     4 pothole
1 alligator_crack                   5 weathering_raveling
2 block_crack                       6 lane_shoulder_drop_off
3 patching                          7 marking_manhole
```

---

## 5. Tugagach

Menga ayting — men:
1. Yorliqlarni tekshiraman (buzuq koordinata, sinf muvozanati, juftlashmagan fayl)
2. `DATA/manifests/qoplama_tiles.csv` manifestiga aylantiraman
3. Datasetga qo'shib, mavjud modeldan **fine-tune** qilaman
4. Block cracking bo'yicha "oldin/keyin" ni **o'lchab** ko'rsataman

---

## 6. Vaqtni qanday taqsimlash

| Bosqich | Vaqt |
|---|---|
| Yuqoridagi ta'riflarni o'qish, 10 ta rasmni sinov uchun yorliqlash | 20 daq |
| **To'xtang, menga 10 tasini ko'rsating** — usulni tasdiqlaymiz | 5 daq |
| Qolgan 150 tasi | 80 daq |
| Tekshirish | 15 daq |

⚠️ **Birinchi 10 tasidan keyin albatta to'xtang.** Agar usul noto'g'ri bo'lsa,
160 tasini qayta qilishdan ko'ra 10 tasida tuzatgan yaxshi.
