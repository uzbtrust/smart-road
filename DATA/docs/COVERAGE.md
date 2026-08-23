# Qamrov: kadr aslida yo'lning qancha qismini o'lchaydi

O'lchov sanasi: 2026-avgust. Manba: `yangizamon_2026-08-03_fwd_pass2` (1 810 m,
286 kadr, 23 km/soat). Kod: `smartroad/survey/sections.py`.

---

## 1. `far_m` — so'rov, natija emas

Ilovada "Measure out to (m)" slayderi 15.0 da turadi. Lekin detektor faqat ROI
ichini qidiradi va osmon kesimi (`sky cut-off`, standarti 0.45) ROI ning
yuqori chegarasini gorizontdan ancha pastga tushiradi.

O'lchangan haqiqiy tasma:

| Kadr o'lchami | Osmon kesimi | So'ralgan | **Haqiqiy tasma** |
|---|---|---|---|
| 1280×720 (video rejimi) | 0.45 | 3–15 m | **3.0–6.8 m** |
| 1920×1080 | 0.45 | 3–15 m | **3.0–6.8 m** |
| 1024×352 (Tehran namunasi) | 0.45 | 3–15 m | 3.8–11.1 m |

Ya'ni 16:9 yozuvda 6.8 metrdan naridagi asfalt umuman qidirilmaydi. Qolgani
`_box_ground_area_m2` dagi qator qirqishida jimgina tushib qoladi.

`effective_band(camera, roi, near_m, far_m)` shu haqiqiy tasmani qaytaradi.
Har qanday qamrov hisobi nominal `far_m` dan emas, shundan boshlanishi kerak.

---

## 2. Natija: HANDOFF §4.3 ning farazi teskari chiqdi

§4.3 kadrlar ustma-ust tushadi va yoriq ikki marta sanaladi deb hisoblagan.
Bu 3–12 m chuqurlikdagi tasma uchun to'g'ri bo'lardi. Haqiqiy tasma esa
**3.83 m**, kadrlar orasi **6.34 m**:

| Tasma | Qamrov | O'lchangan | Ko'rilmagan |
|---|---|---|---|
| Nominal 3–15 m | 100.0 % | 1 819 m | 0 m |
| **Haqiqiy 3–6.8 m** | **44.8 %** | 811 m | **1 000 m** |

Bu yozuvda asosiy muammo ortiqcha sanash emas — **ko'chaning yarmidan ko'pi
qidiruv tasmasiga tushmagan**. Ustma-ustlik faqat mashina sekinlashgan
joylarda bor (286 kadrdan 87 tasi qirqildi, 4 tasi butunlay tashlandi).

⚠️ Shuning uchun bo'lak darajasidagi har qanday zichlik qamrov ulushi bilan
birga aytilishi shart. `Section.coverage_fraction` aynan shuning uchun bor.

---

## 3. To'liq qamrovga ikki yo'l

**A. Osmon kesimini pasaytirish** — bepul, qo'shimcha hisob talab qilmaydi:

| Osmon kesimi | Tasma | Qamrov |
|---|---|---|
| 0.45 | 3.0–6.8 m | 44.8 % |
| 0.35 | 3.0–10.4 m | 81.3 % |
| **0.25** | **3.0–15.0 m** | **100 %** |

**B. Tez-tez namuna olish** — hisob narxi oshadi:

| Interval | Kadrlar | Qamrov |
|---|---|---|
| 1.0 s | 286 | 44.8 % |
| 0.5 s | 573 | 83.9 % |
| **0.35 s** | **818** | **100 %** |

---

## 4. Qaysi biri to'g'ri

A varianti bepul, lekin **bepulligi aldamchi**. Osmon kesimini pasaytirish
detektorni kadrning yuqori qismida ishlashga majbur qiladi, u yerda asfalt
kichik va nuqson piksellari kam. §4.2 da o'lchanganidek, 1080p da 10 mm yoriq
3.5 m da ≈ 4 piksel, 9 m da 2 pikseldan kam. 15 m dagi "aniqlash" geometrik
jihatdan qamrovga kiradi, lekin o'lchov sifatida ishonchsiz.

Shuning uchun tavsiya: **osmon kesimi 0.45 da qolsin, namuna oralig'i 0.35 s
ga tushirilsin.** Qamrov 100 % bo'ladi va har bir o'lchangan metr ishonchli
tasma ichida bo'ladi. Narxi — 2.9 barobar hisob, bu esa bir martalik so'rov
uchun arzimas.

4K yozuvda (`IMG_9769/9770.MOV`, 3840×2160) ishonchli tasma uzunroq bo'ladi va
ikkala parametr ham yumshaydi — lekin ularda GPX yo'q, shuning uchun hozircha
kilometrajga bog'lab bo'lmaydi.
