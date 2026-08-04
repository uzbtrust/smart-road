# Yangizamon ko'chasi — PCI hisobi

Manba: `Baxodir.xlsx` (professorning qo'lda o'lchagan tadqiqoti, 12 varaq = 12 bo'lak)
Kod: `smartroad/pci/from_survey.py`

---

## 1. Nima qilindi

Excel'da **zichliklar bor, PCI yo'q**. Bu professorning maqolasidagi jumlaga mos:

> *"the standard deduct-value curves and corrected deduct-value procedure were not applied, and therefore a PCI value was not calculated"*

Uning zichliklarini ASTM D6433 ning deduct egri chiziqlaridan o'tkazib, **12 ta bo'lak uchun PCI hisoblandi**.

---

## 2. Natija

| Bo'lak | Yo'nalish | CDL | **PCI** | Reyting | Yetakchi nuqson |
|---|---|---:|---:|---|---|
| S1 | A | 28.37 | **52.3** | Poor | Bo'ylama/ko'ndalang yoriq L 10.3% |
| S2 | A | 28.89 | **64.6** | Fair | Bloksimon yoriq L 11.2% |
| S3 | A | 29.03 | **61.1** | Fair | Bo'ylama/ko'ndalang yoriq L 9.4% |
| S4 | A | 49.38 | **33.1** | Very Poor | Bloksimon yoriq M 13.5% |
| S5 | A | 43.72 | **64.8** | Fair | Bloksimon yoriq L 18.6% |
| S6 | A | 43.28 | **62.7** | Fair | Bloksimon yoriq L 22.4% |
| S7 | B | 33.98 | **26.6** | Very Poor | Bloksimon yoriq L 20.1% |
| S8 | B | 60.44 | **32.4** | Very Poor | To'rsimon yoriq M 18.6% |
| S9 | B | 16.82 | **45.6** | Poor | Yamoq L 4.5% |
| S10 | B | 23.54 | **58.3** | Fair | Yamoq L 11.3% |
| S11 | B | 70.55 | **45.6** | Poor | Bloksimon yoriq L 35.2% |
| S12 | B | 39.44 | **69.9** | Fair | Bloksimon yoriq L 19.6% |

**Butun ko'cha o'rtacha PCI = 51.4 (Poor)**
A yo'nalishi **56.4** · B yo'nalishi **46.4**

Professorning "B yo'nalishi yomonroq" xulosasi tasdiqlandi va aniqlashtirildi: CDL bo'yicha farq 9.96% edi, PCI bo'yicha **10 punkt**.

---

## 3. ⭐ Asosiy topilma: CDL va PCI eng yomon bo'lakni boshqacha ko'rsatadi

| | Eng yomon bo'lak |
|---|---|
| **CDL bo'yicha** | **S11** (CDL 70.55) |
| **PCI bo'yicha** | **S7** (PCI 26.6) |

Nega farq qiladi:

- **S11** — 35.2% bloksimon yoriq, lekin **past darajada**. Zichligi katta, shuning uchun CDL yuqori. Lekin past darajali bloksimon yoriqning deduct egri chizig'i yumshoq.
- **S7** — bloksimon yoriq 20.1%, lekin qo'shimcha **yuqori darajali chuqurchalar** bor. Chuqurcha eng og'ir deduct beradi.

CDL — oddiy yig'indi: u 1% yuqori darajali chuqurchani 1% past darajali yoriq bilan **teng** hisoblaydi. PCI esa har bir tur va daraja uchun alohida egri chiziqdan o'tkazadi.

Bu professorning o'z cheklovini tasdiqlaydi:

> *"CDL has no calibrated scale, deduct-value weighting, or condition rating comparable to standardized PCI."*

Amaliy ma'nosi: ta'mirlash byudjeti CDL bo'yicha taqsimlansa, **S11 ga birinchi borilardi**. PCI bo'yicha esa **S7 shoshilinchroq**.

---

## 4. ⚠️ Excel'da topilgan 6 ta xato

Har biri maqoladagi nashr etilgan CDL bilan tekshirildi — **oltitasi ham tugal izohlandi**, ya'ni maqoladagi raqamlar to'g'ri, Excel'dagi kataklar buzilgan.

| Varaq | Nuqson | Excel'da | Bo'lishi kerak | Xato turi |
|---|---|---:|---:|---|
| Лист1 | bumps and sags L | 0.0256 | **0.2562** | 10 barobar past |
| Лист4 | block cracking H | 84.0 | **3.077** | maydonga bo'linmagan |
| Лист6 | long/trans L | 0.5779 | **5.779** | 10 barobar past |
| Лист7 | alligator L | 0.7165 | **7.165** | 10 barobar past |
| Лист7 | potholes H | *bo'sh* | **0.745** | katak to'ldirilmagan |
| Лист8 | block cracking L | 1.4684 | **14.684** | 10 barobar past |
| Лист12 | long/trans L | *bo'sh* | **1.115** | katak to'ldirilmagan |

Tekshirish usuli: har varaq uchun `zichlik → CDL` yig'indisi hisoblanib, maqoladagi qiymat bilan solishtirildi. Tuzatishdan keyin **12 tadan 12 tasi** mos keldi.

---

## 5. Qabul qilingan farazlar

**1. Bo'lak maydonlari har xil.** Maqolada "har biri 300 m" deyilgan, lekin Excel'dagi `miqdor / zichlik` nisbati har varaqda boshqa maydon beradi:

| S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | S10 | S11 | S12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3240 | 3405 | 2730 | 2730 | 4830 | 2324 | 2730 | 1444 | 3569 | 3117 | 1875 | 2062 |

Har varaq ichida bu izchil, shuning uchun tekshirilgan maydon (inspected area) haqiqatan farq qilgan deb qabul qilindi — ASTM ham aynan tekshirilgan maydonni talab qiladi.

**2. Chuqurchalar maydon sifatida yozilgan.** Qiymatlar butun son emas (20.34, 9.79), demak m². ASTM esa **dona** talab qiladi. Standartning o'z konversiyasi qo'llanildi (X1.17.1.2): `maydon ÷ 0.5 m² = ekvivalent dona`.

**3. Birliklar konvertatsiya qilindi.** Deduct egri chiziqlari **futda** chizilgan. Maydon uchun farq yo'q (m²/m² = ft²/ft²), lekin:
- chiziqli nuqson: **×0.3048**
- chuqurcha (dona): **×0.0929**

Bu **hal qiluvchi**. Konvertatsiyasiz hisoblansa:

| | To'g'ri | Konvertatsiyasiz |
|---|---:|---:|
| S3 | 61.1 | 35.3 |
| S7 | 26.6 | **0.0** |
| S9 | 45.6 | 19.0 |

Ya'ni **26 PCI punktgacha xato**. Professor ertaga qo'lda hisoblaganda buni hisobga olishi kerak — aks holda ko'cha bor-yo'g'idan ancha yomon chiqadi.

---

## 6. Ertaga professorning raqamlari kelganda

Ikki ehtimol:

- **Mos kelsa** — ikkala hisob ham mustaqil tasdiqlanadi. Bizning dvigatelimiz ASTM ning rasmiy misolida (PCI=49) va professorning dala tadqiqotida ham to'g'ri ishlagan bo'ladi.
- **Farq qilsa** — sabab deyarli aniq birliklarda bo'ladi (5-bo'lim). Farqning kattaligi 3.28× yoki 10.76× ga yaqin bo'lsa, bu tasdiqlaydi.

Ikkala holat ham foydali.

---

## 7. ⭐ Professorning o'z PCI hisobi topildi (2026-08-04)

Excel'ning **o'ng tomonidagi ustunlarda**, nuqson jadvallaridan ancha narida,
har bir varaqda **TDV / CDV / PCI** yozuvlari turgan ekan. Ular bir necha ustun
bo'sh joydan keyin joylashgani uchun ilgari e'tibordan chetda qolgan.

Ya'ni maqoladagi *"a PCI value was not calculated"* jumlasi Excel'ga to'g'ri
kelmaydi — **12 tadan 12 tasi uchun PCI hisoblangan**. Hamma varaqda
`PCI = 100 − CDV` munosabati saqlanadi.

| Bo'lak | Professor TDV | Bizning TDV | Professor CDV | Bizning CDV | **Professor PCI** | **Bizning PCI** | Farq |
|---|---:|---:|---:|---:|---:|---:|---:|
| S1 | 114.5 | 94.4 | 50 | 47.7 | **50** | **52.3** | +2.3 |
| S2 | 77.5 | 62.2 | 39 | 35.4 | **61** | **64.6** | +3.6 |
| S3 | 118.5 | 69.1 | 56 | 38.9 | **44** | **61.1** | +17.1 |
| S4 | 186.7 | 143.0 | 80 | 66.9 | **20** | **33.1** | +13.1 |
| S5 | 84.2 | 64.1 | 42 | 35.2 | **58** | **64.8** | +6.8 |
| S6 | 73.0 | 61.5 | 46 | 37.3 | **54** | **62.7** | +8.7 |
| S7 | 148.0 | 134.3 | 70 | 73.4 | **30** | **26.6** | −3.4 |
| S8 | 105.5 | 117.5 | 60 | 67.6 | **40** | **32.4** | −7.6 |
| S9 | 122.1 | 115.2 | 60 | 54.4 | **40** | **45.6** | +5.6 |
| S10 | 112.0 | 83.5 | 56 | 41.7 | **44** | **58.3** | +14.3 |
| S11 | 106.0 | 103.9 | 56 | 54.4 | **44** | **45.6** | +1.6 |
| S12 | 69.0 | 52.6 | 34 | 30.1 | **66** | **69.9** | +3.9 |

O'rtacha mutlaq farq **7.3 PCI punkti**, korrelyatsiya **0.87**.
12 tadan **9 tasi ±10 punkt ichida**, 5 tasi ±5 ichida.

### Farq qayerdan kelyapti — o'lchandi

Farq **CDV tuzatish bosqichida emas, deduct bosqichida**: TDV o'rtacha 18 %
farq qiladi va bizniki **12 tadan 11 tasida tizimli ravishda pastroq**.
Tizimli bo'lgani uchun bu tasodifiy o'qish xatosi emas.

Sinov: TDV ni **birlik konversiyasisiz** (metrik zichlikni to'g'ridan-to'g'ri
imperial egri chiziqqa berib) hisoblab ko'rildi.

| | Konversiya bilan | Konversiyasiz |
|---|---:|---:|
| Professor TDV bilan o'rtacha mutlaq farq | 20.0 | **13.1** |

Chiziqli nuqson ulushi katta bo'lgan bo'laklarda moslik deyarli mukammal
bo'lib qoladi:

| Bo'lak | Chiziqli ulush | Farq (konversiya bilan) | Farq (konversiyasiz) |
|---|---:|---:|---:|
| S1 | 30 % | −20.1 | **+1.6** |
| S3 | 32 % | −49.4 | **−3.0** |
| S5 | 30 % | −20.1 | **−1.3** |
| S11 | 0 % | −2.1 | −2.1 |

S11 da chiziqli nuqson umuman yo'q — va u yerda ikkala usul ham bir xil natija
beradi, professor bilan farq atigi 2.1.

➜ **Xulosa: professor chiziqli nuqsonlar uchun fut↔metr konversiyasini
qo'llamagan.** Aynan 5-bo'limda ogohlantirilgan xato. Bu uning PCI qiymatlarini
tizimli ravishda **pasaytiradi** (ko'chani bor-yo'g'idan yomonroq ko'rsatadi).

S7, S8, S9 da esa teskarisi — u yerda chuqurcha va qoplama surilishi ustun,
va konversiyasiz hisob yomonroq mos keladi. Ya'ni professor maydon va dona
tipidagi nuqsonlarni to'g'ri ishlagan, faqat chiziqlilarni emas.

### ⚠️ Bizning tomonda topilgan xato (tuzatildi)

Xuddi shu tekshiruv paytida `parse_workbook` da xato topildi: severity qatoridagi
**hamma** sonni o'qib, oxirgisini "jami" deb olardi. Lekin o'sha qatorlarda
professorning TDV/CDV/PCI ustunlari ham turibdi.

Лист2 da bu quruq `M` qatoriga `PCI = 61` qiymatini yozib qo'ygan va yo'q
nuqsonni (to'rsimon yoriq M, DV 27.4 — bo'lakdagi eng katta deduct) o'ylab
topgan. Natijada S2 ning PCI si 64.6 o'rniga 51.9 chiqqan.

Tuzatish: `_measurements()` endi **birinchi matnli katakda to'xtaydi**.
Tuzatishdan keyin 12 tadan 12 tasi shu hujjatdagi qiymatlarni qaytaradi.

Qayta tekshirish:

```
.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from pathlib import Path
from smartroad.pci.from_survey import parse_workbook, corrected_densities, pci_from_densities, surveyor_pci
prof = surveyor_pci(Path('Baxodir.xlsx'))
for i, s in enumerate(parse_workbook(Path('Baxodir.xlsx')), 1):
    pci, r, cdv, q = pci_from_densities(corrected_densities(s))
    print(f'S{i:<3d} biz {pci:5.1f}   professor {prof[s.name][\"PCI\"]:5.0f}')
"
```
