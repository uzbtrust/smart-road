# Professor bilan yorliqlash seansi — protokol

**Vaqt:** professor bilan ~35 daqiqa + siz yolg'iz ~70 daqiqa
**Qachon:** hakatonning 1-kuni kechqurun yoki 2-kuni ertalab (kechi bilan 7-avgust tushgacha)
**Material:** shu papkadagi `varaq_01.jpg` … `varaq_08.jpg` va `javob_varaqasi.csv`

---

## Asosiy g'oya: ikkita ishni ajratamiz

Ikki xil ish bor va ular bir xil emas:

| Ish | Kim qiladi | Nega |
|---|---|---|
| **"Bu qaysi nuqson turi?"** | **Professor** | ASTM tajribasi kerak, bu uning kasbi |
| **"Box qayerga chiziladi?"** | **Siz** | mexanik ish, tajriba kerak emas |

Ko'p odam ikkalasini birga qiladi va professorning 2 soatini yeydi. Biz ajratamiz:
professor faqat **sinf aytadi**, box chizishni siz keyin qilasiz.

➜ Professorning vaqti **2 soatdan 35 daqiqaga** tushadi.

---

## 1-bosqich · Kalibrovka (10 daqiqa)

`varaq_01.jpg` ni oching. Unda 20 ta parcha, har birida katta raqam.

Professordan **birinchi 5-6 tasini ovoz chiqarib** tasniflashini so'rang — **va nega
shunday deganini tushuntirishini**.

Bu seansning **eng qimmatli qismi**. Maqsad raqam yig'ish emas, uning mezonini
o'rganish. So'rash kerak bo'lgan savollar:

- "Buni bloksimon deyishingizga nima sabab bo'ldi?"
- "Bloksimon bilan to'rsimonni siz qanday ajratasiz?"
- "Bu yerda bir nechta yoriq bormi yoki bitta yoriqning tarmog'imi?"

Uning javoblarini **o'z so'zlari bilan** yozib oling. Menga o'sha yozuv kerak —
qolgan datasetni ham shu mezon bo'yicha tekshiraman.

---

## 2-bosqich · Tez tasniflash (25 daqiqa)

Endi 8 ta varaqni ketma-ket ko'rasiz. Professor qaraydi, sinf aytadi, siz yozasiz.

`javob_varaqasi.csv` faylini oching (Excel yoki Numbers bilan) va `sinf` ustunini
to'ldiring. Qisqartma yozsangiz ham bo'ladi:

| Yozing | Sinf | ASTM |
|---|---|---|
| `bo` | bo'ylama/ko'ndalang yoriq | №10 |
| `to` | to'rsimon (alligator) | №1 |
| `bl` | bloksimon (block) | №3 |
| `ya` | yamoq (patching) | №11 |
| `ch` | chuqurcha (pothole) | №13 |
| `ti` | tishlashish (weathering/raveling) | №19 |
| `-` | nuqson yo'q / aniq emas | — |
| `?` | professor ikkilanmoqda | — |

**Qoidalar:**

- **Bahslashmang, muhokama qilmang.** Professor aytdi — yozdingiz — keyingisi.
- Professor **ikkilansa** → `?` qo'ying va o'ting. Vaqt sarflamang. Keyin men uni
  o'quv to'plamiga qo'shmayman, shubhali yorliq yo'qdan yomonroq.
- Bitta parchada **ikki xil nuqson** bo'lsa → ikkalasini vergul bilan yozing: `bo,to`
- Professor **bizning ro'yxatda yo'q** turni aytsa (masalan "chok aksi yorig'i",
  ASTM №8) → `izoh` ustuniga o'z nomi bilan yozing. Zo'rlab noto'g'ri sinfga
  tiqmang — men keyin hal qilaman.

---

## 3-bosqich · Jiddiylik (bonus — imkoni bo'lsa)

Agar professor ulguradigan bo'lsa, har parcha uchun **L / M / H** ham so'rang va
`izoh` ustuniga yozing (masalan `bl H`).

**Bu juda qimmat.** Bizda hozir jiddiylik yorliqlari deyarli yo'q, holbuki PCI
uchun jiddiylik **majburiy** — ASTM da bir xil zichlikdagi past va yuqori darajali
nuqson butunlay boshqa deduct beradi.

ASTM chegaralari (professorga eslatma sifatida):

| Nuqson | L (past) | M (o'rta) | H (yuqori) |
|---|---|---|---|
| Bo'ylama/ko'ndalang, bloksimon | **< 10 mm** | 10–75 mm | **> 75 mm** |
| To'rsimon | ingichka, tarmoqlanmagan | to'r shakllangan | bo'laklar ko'chgan |
| Yamoq | yaxshi holatda | o'rtacha buzilgan | almashtirish kerak |

Parchalarda masshtabni chamalash uchun: **asfalt shag'ali ≈ 1–2 sm**.
Ya'ni 10 mm ≈ kichik shag'al donasining kengligi.

---

## 4-bosqich · Box chizish (siz yolg'iz, ~70 daqiqa)

Endi sinf ma'lum, o'ylash kerak emas. makesense.ai da har parchani ochib box chizasiz.

**Box qayerga:**

| Professor aytgan sinf | ASTM birligi | Box qanday |
|---|---|---|
| bloksimon, to'rsimon, yamoq, tishlashish | **m²** (maydon) | butun zararlangan **maydonga bitta** box |
| bo'ylama/ko'ndalang | **metr** (uzunlik) | **har bir yoriqqa alohida**, yoriq bo'ylab tor box |
| chuqurcha | **dona** | har bir teshikka alohida box |

Maydon nuqsonlarida ko'pincha **butun parcha** zararlangan bo'ladi — u holda box
deyarli butun kadrni qoplaydi, bu normal. Parchalar shunday tanlangan.

`-` yoki `?` belgilangan parchalarga box **chizmang**, shunchaki o'tib keting.
Box'siz rasm ham foydali — model "bu yerda hech narsa yo'q" deb o'rganadi.

**Saqlash:** Actions → Export Annotations → *A .zip package containing files in
YOLO format* → arxivni oching → `.txt` fayllarni
`LABEL_TASK/block_crack/labels/` ichiga qo'ying.

---

## 5-bosqich · Menga bering

Kerak bo'lgan narsalar:
1. To'ldirilgan `javob_varaqasi.csv`
2. `labels/` ichidagi `.txt` fayllar
3. 1-bosqichda yozib olgan professorning mezonlari

Men shundan keyin:
- yorliqlarni tekshiraman (buzuq koordinata, juftlashmagan fayl, sinf muvozanati)
- datasetga qo'shaman
- mavjud modeldan **fine-tune** qilaman (1–2 soat)
- bloksimon yoriq bo'yicha **"oldin / keyin"** ni raqam bilan ko'rsataman

---

## Nega bu hakaton uchun muhim

Professorning Yangizamon tadqiqotida **bloksimon yoriq — eng ko'p uchraydigan
nuqson, umumiy CDL ning 46 %**. 12 bo'lakning 7 tasida yetakchi nuqson aynan shu.

Bizning butun datasetimizda esa bloksimon yoriq uchun **atigi 61 ta box** bor.
Ya'ni model professorning ko'chasidagi asosiy nuqsonni ko'rmaydi.

Bu seans shu teshikni yopadi. Va yana bir narsa: **munozara qilaman deb qo'rqmang** —
professor bizning sinflarimizga rozi bo'lmasligi ham natija. Uning e'tirozi
hisobotga tushadi va bu kuch bo'ladi, zaiflik emas.
