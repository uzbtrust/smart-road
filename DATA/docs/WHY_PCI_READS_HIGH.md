# Nega avtomatik PCI professorning bahosidan yuqori chiqadi

2026-08-05. Professor kamera balandliklarini o'lchab berdi va avtomatik PCI
kutilgandan baland chiqayotganini aytdi. Quyida — taxmin emas, o'lchov.

---

## 1. Kamera balandligi tuzatildi

Professor bergan raqamlar (Ford old g'ildiragi o'qiga nisbatan):

| | Asfaltgacha | O'qqacha (gorizontal) |
|---|---:|---:|
| Ford mobil laboratoriya kamerasi | **285 sm** | 130 sm |
| Telefon kamerasi | **170 sm** | 40 sm |
| O'q balandligi | 45 sm | — |

Videolarni telefon olgan, ya'ni **h = 1.70 m**. Ilgari 1.95 m ishlatilardi.

### Eski qiymat qayerdan kelgan va nega noto'g'ri edi

`SURVEY/.../README.md` da yon masshtab v = 1000 qatorida **2.4 mm/px** deb
o'lchangan. U raqam yo'lak enini **3.5 m** deb faraz qilib chiqarilgan.

Geometriyani teskari yechsak (f₃₅ = 25 mm, gorizont v ≈ 150, pitch 16.30°):

| Balandlik | Yon masshtab | Shu masshtabda yo'lak eni |
|---:|---:|---:|
| 1.70 m | 2.08 mm/px | **3.04 m** |
| 1.95 m | 2.39 mm/px | 3.49 m |

Ya'ni 1.95 m faqat yo'lak 3.5 m bo'lganda to'g'ri bo'lardi. Lentaga ko'ra kamera
1.70 m da, va shunda o'sha piksel eni **3.04 m** ga to'g'ri keladi — O'zbekiston
shahar ko'chalari uchun odatiy en. **Lenta o'lchovi ustun.**

---

## 2. Lekin balandlik PCI ni deyarli o'zgartirmaydi

15 kadrlik Yangizamon klipida:

| Balandlik | O'rtacha PCI | O'lchangan sirt | Umumiy zichlik |
|---:|---:|---:|---:|
| 1.70 m | **80.7** | 28.8 m² | 5.45 % |
| 1.95 m | 81.4 | 40.2 m² | 5.67 % |

Farq **0.7 PCI punkti**. Balandlik xatosi PCI ning yuqori chiqishiga sabab emas.

---

## 3. Haqiqiy sabab — model nuqsonlarni topmayapti

Professor maqolasida qayd etilgan **yetakchi** nuqson zichliklari:

| Bo'lak | Nuqson | Zichlik |
|---|---|---:|
| S11 | bloksimon yoriq L | **35.15 %** |
| S6 | bloksimon yoriq L | 22.39 % |
| S7 | bloksimon yoriq L | 20.11 % |
| S12 | bloksimon yoriq L | 19.60 % |
| S8 | to'rsimon yoriq M | 18.62 % |
| S10 | yamoq L | 11.31 % |
| S1 | bo'ylama/ko'ndalang L | 10.34 % |
| S3 | bo'ylama/ko'ndalang L | 9.40 % |

**O'rtacha 18.4 %** — va bu faqat har bo'lakning *bitta* yetakchi nuqsoni.

Bizning kadrlarda **hamma** nuqson turi qo'shilganda: **5.4 %**.

➜ Model taxminan **3.4 barobar kam** nuqson qayd qiladi. PCI = 100 − CDV
bo'lgani uchun kam nuqson to'g'ridan-to'g'ri yuqori PCI degani.

### Qaysi sinf yo'qolyapti — aniq raqam

15 kadrda jami 38 ta aniqlash:

| Sinf | Topildi |
|---|---:|
| Bo'ylama/ko'ndalang yoriq | 29 |
| Yo'l belgisi / quduq *(baholanmaydi)* | 7 |
| Chuqurcha | 2 |
| Yamoq | 0 |
| Yemirilish | 0 |
| **Bloksimon yoriq** | **0** |

Professor bo'yicha esa bloksimon yoriq:

- umumiy CDL ning **46.33 %**
- 12 bo'lakdan **7 tasida yetakchi nuqson**

**Model o'sha ko'chaning asosiy nuqsonini umuman ko'rmayapti.**

### Nega ko'rmaydi

Datasetda bloksimon yoriq uchun **59 ta train box** bor — 103 968 tadan, ya'ni
**0.06 %**. Validatsiyada 2 ta. Bu sinf o'qitilmagan darajada kam.

Bu `BLOCK_CRACK_GAP.md` da oldindan aniqlangan bo'shliq. Endi u haqiqiy
kadrlarda raqam bilan tasdiqlandi.

---

## 4. Xulosa — professorga aytiladigan gap

PCI yuqori chiqishining sababi standart matematikasi ham, kamera geometriyasi
ham emas. Ikkalasi ham tekshirilgan:

- ASTM dvigateli standartning o'z misolini qaytaradi (nashr etilgan 49 ga qarshi 48.6)
- Kamera balandligi tuzatildi va u PCI ni 0.7 punktga o'zgartiradi

Sabab — **detektor uning ko'chasidagi asosiy nuqsonni ko'rmasligi**. U 18.4 %
bloksimon yoriq qayd qilgan joyda model 0 % ko'radi.

Ya'ni hozirgi avtomatik PCI **optimistik** va shunday deb qabul qilinishi kerak.
Uni to'g'rilash yo'li bitta: **bloksimon yoriq uchun yorliqlangan ma'lumot**.

### Keyingi qadam

`LABEL_TASK/` paketi aynan shu uchun tayyorlangan edi — QOPLAMA rasmlaridan
kesilgan 160 ta parcha, professor sinfini aytadi, box keyin chiziladi. Paket
hakaton bekor bo'lgach o'chirildi, lekin manba rasmlar `DATA/raw/qoplama_tashkent`
da turibdi, ya'ni qayta yig'ish mumkin.

160 ta yangi parcha mavjud 59 ta box ustiga qo'shilsa — taxminan **3.7 barobar**
o'sish. Undan keyin fine-tune qilib, xuddi shu 15 kadrda oldin/keyin o'lchash
kerak.
