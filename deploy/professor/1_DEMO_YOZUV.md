# 1 — Demo ekran yozuvi

**Kim bajaradi:** Raximjon Soataliyev + montajchi
**Nima chiqadi:** 4–6 daqiqalik montajsiz ekran yozuvi (xom material)
**Bu nima uchun:** video pitchning ichidagi hamma "ishlayotgan" kadrlar shundan
kesiladi. Yaxshi yozuv boʻlmasa, pitch ham boʻlmaydi.

⚠️ **Bu tayyor video emas.** Bu — xom material. Uni kesish, tezlashtirish va
ovoz ustiga qoʻyish keyingi bosqichda (`2_VIDEO_PITCH.md`).

---

## A. Yozishdan oldin — texnik tayyorgarlik

**Ekran:**

| Sozlama | Qiymat | Nega |
|---|---|---|
| Ruxsat | **1920×1080** | 4K yozib keyin kichraytirish shart emas; matn 1080p da aniqroq chiqadi |
| Kadr chastotasi | **60 fps** | Sichqoncha harakati va sahifa aylantirish silliq koʻrinadi |
| Brauzer masshtabi | **100 %** | 110 % da maket siljiydi |
| Tema | **Qorongʻi** | Sayt qorongʻi rejimda ishlab chiqilgan |

**Ekranni tozalash — bularsiz yozuv qayta olinadi:**

- Barcha bildirishnomalarni oʻchiring (macOS: *Focus → Do Not Disturb*)
- Brauzerda **yangi toza profil** oching — xatcho'plar paneli koʻrinmasin
- Faqat bitta tab. Boshqa tablar sarlavhasi kadrda qolmasin
- Ish stoli fonida shaxsiy narsa boʻlmasin
- Telegram, pochta, kalendar — yopiq
- ⚠️ **Kadrda hech qanday shaxsiy maʼlumot boʻlmasin:** email manzili,
  telefon raqami, brauzer tarixi, avtomatik toʻldirish takliflari

**Yozib olish dasturi:** macOS'da QuickTime (*File → New Screen Recording*)
yoki OBS. OBS aniqroq — kadr chastotasini qoʻlda belgilash mumkin.

**Ovoz:** ❌ yozuv paytida **gapirmang**. Ovoz alohida yoziladi (2-fayl).
Faqat ekran.

**Sichqoncha:** sekin va maqsadli harakatlaning. Aylanma, ikkilanuvchi harakat
montajda yomon koʻrinadi. Bosishdan oldin bir soniya toʻxtang.

---

## B. Shot list — nima yozilishi kerak

Har bir bandni **alohida fayl** qilib yozing. Bir uzun yozuvdan koʻra oʻn qisqa
fayl montajchi uchun ancha qulay. Nomlash: `01_sayt_hero.mov`, `02_argument.mov` …

### Blok 1 — Sayt (2 daqiqa atrofida)

| № | Nima yoziladi | Davomiyligi | Izoh |
|---|---|---|---|
| 01 | Sayt ochiladi, hero kadr toʻliq koʻrinadi | 8 s | Sahifa yuklanishini boshidan yozing |
| 02 | Sekin pastga aylantirish — argument boʻlimi | 12 s | S7/S11 taqqoslash toʻliq kadrga tushsin |
| 03 | Argument boʻlimida **toʻxtash** | 6 s | Montajchi shu yerda matn qoʻyadi |
| 04 | Toʻrt bosqich boʻlimi | 10 s | |
| 05 | Validatsiya raqamlari va 12 boʻlak jadvali | 10 s | |
| 06 | Cheklovlar boʻlimi | 8 s | |
| 07 | **Til almashtirish: UZ → RU → EN** | 12 s | Har birida 3 soniya turing. Bu uch tillilikning isboti |

### Qaysi namunalarni tanlash kerak — aniq roʻyxat

Ilovaning **Sample** roʻyxatidan aynan shu uchtasini tanlang. Ular saytda
koʻrsatilgan kadrlarning oʻzi, ya'ni video bilan sayt bir xil rasmni koʻrsatadi
va hakam ikkisini bogʻlay oladi.

| Kadr | Roʻyxatda qanday koʻrinadi | Kutilgan natija |
|---|---|---|
| **Fotosurat 1** | `attain tehran  Attain SMP WS v2 000800` | PCI **36.5 — Juda yomon** · 4 aniqlash · 28.9 m² |
| **Fotosurat 2** | `yangizamon forward 160s` | PCI **83.7 — Qoniqarli** · Toshkent, 1920×1080 |
| **Video** | `yangizamon 15s` | 15 soniya, tahlil ~45–60 s davom etadi |

⚠️ **`000795` ni tanlamang.** U PCI **0 — Failed** beradi. Bu dasturning xatosi
emas: oʻsha kadrda toʻrsimon yoriq shunchalik zichki, chegirmalar yigʻindisi 100
shiftiga urilади va PCI nolga tushadi — ASTM aynan shunday ishlaydi. Lekin
ekranda `0` va `Failed` koʻringani buzuq dasturdek oʻqiladi, shuning uchun demo
uchun yaramaydi. `000528` ham oʻrta jiddiylikda 12.9 beradi va yuqorida nolga
tushadi — uni ham tanlamang.

**12-kadr (jiddiylik slayderi) uchun `000800` ni ishlating** — faqat oʻshanda
uchala qiymat ham noldan katta va bir-biridan aniq farq qiladi:
past **51.5** → oʻrta **36.5** → yuqori **20.5**.

Fayllar repoda: `samples/` papkasida. Ularni alohida yuklab olish **shart emas** —
ilovaning oʻzida tayyor turibdi, roʻyxatdan tanlansa boʻldi.

Saytdagi kadr esa `reports/demo/tiled_4k_fwd_160s.jpg` — bu `yangizamon
forward 160s` ning aniqlangan (ramkalar chizilgan) varianti. Ya'ni videoda
tomoshabin saytdagi rasmning qanday hosil boʻlganini koʻradi.

---

### Blok 2 — Ilova, fotosurat rejimi (2 daqiqa atrofida)

| № | Nima yoziladi | Davomiyligi | Izoh |
|---|---|---|---|
| 08 | Namuna rasm tanlanadi, natija chiqadi | 15 s | Kutish vaqtini kesmang — halol koʻrinsin |
| 09 | Aniqlash qatlamiga yaqinlashish | 8 s | Ramkalar va sinf nomlari oʻqilsin |
| 10 | Baho kartasi va yetti bandli shkala | 8 s | |
| 11 | **Deduct zanjiri jadvali** | 12 s | Eng muhim kadr. Zichlik → chegirma → tuzatilgan → PCI |
| 12 | **Jiddiylik slayderi**: past → oʻrta → yuqori | 12 s | `000800` da: 51.5 → 36.5 → 20.5 |
| 13 | **Kamera balandligi**: 1.70 → 2.20 → 1.70 | 12 s | PCI siljishini koʻrsating. Bu — halollik dalili |
| 14 | **Plitkali inferens**: yoqilgan → oʻchirilgan → yoqilgan | 15 s | Aniqlashlar yoʻqolib qaytishi koʻrinsin |

### Blok 3 — Ilova, video rejimi (1 daqiqa atrofida)

| № | Nima yoziladi | Davomiyligi | Izoh |
|---|---|---|---|
| 15 | 15 soniyalik klip tanlanadi, tahlil boshlanadi | 20 s | Jarayonni kesmang |
| 16 | Holat tasmasi toʻliq chiqadi | 10 s | Yashildan qizilgacha oʻtish koʻrinsin |
| 17 | Eng yomon kadr bosiladi | 10 s | |

### Blok 4 — Yuklash (Upload) — **eng muhim blok**

Bu blok butun demoning eng ishonarli qismi. Namunalar oldindan tayyorlangan
boʻlishi mumkin — yuklangan fayl esa yoʻq. Hakam shu yerda tizim haqiqatan
ishlayotganiga ishonadi.

Fayllar alohida yuboriladi (`demo_uploads/` papkasi). Ular namunalar
roʻyxatida **yoʻq** — bu ataylab, chunki yuklash yoʻli aynan shu bilan
isbotlanadi.

| № | Nima yoziladi | Davomiyligi | Izoh |
|---|---|---|---|
| 18 | **Upload** tanlanadi, `upload_yangizamon_reverse_frame.jpg` yuklanadi | 15 s | Fayl nomi va hajmi kadrda koʻrinsin |
| 19 | Natija chiqadi | 12 s | PCI **69.7 — Qoniqarli**, 8 ta aniqlash, 29 m² |
| 20 | **Drive video → Upload**, `upload_yangizamon_reverse_15s.mp4` | 15 s | 12 MB. Yuklanish jarayoni koʻrinsin |
| 21 | Video tahlili tugaydi, holat tasmasi chiqadi | 15 s | PCI 55 dan 100 gacha oʻzgaradi |

**Nega aynan bu fayllar:** ikkalasi ham Yangizamon koʻchasining **teskari
yoʻnalishdagi** oʻtishidan olingan, namunalar esa oldinga yoʻnalishdan. Yaʼni
bu — hech qachon koʻrsatilmagan, lekin oʻsha koʻchaning oʻzi.

**Aytishga arzigan gap:** namunalar `Serious 13` beradi, yuklangan fayl esa
`Qoniqarli 69.7`. Bu tasodif emas va buni pitchda taʼkidlash kerak — tizim
hamma yoʻlni yomon demaydi, u **farqlaydi**.

---

## C. Yozib boʻlgach — montajchiga nima beriladi

1. **Barcha `.mov` fayllar** — kesilmagan, siqilmagan
2. **Bu fayl** — shot list bilan
3. `2_VIDEO_PITCH.md` — u yerda qaysi kadr qaysi jumla ostida turishi yozilgan
4. **Logotip**: `Logo/SVG/` papkasi (vektor — istalgan oʻlchamda aniq)
5. **Brend ranglari:** toʻq sariq `#F8A519`, koʻmir `#3A3A3C`

**Yozishdan oldin sizga kerak boʻladigan ikkita fayl** (18–21 kadrlar uchun):

| Fayl | Hajmi | Kutilgan natija |
|---|---|---|
| `upload_yangizamon_reverse_frame.jpg` | 298 KB | PCI 69.7 · Qoniqarli · 8 aniqlash · 29 m² |
| `upload_yangizamon_reverse_15s.mp4` | 12 MB | 15 kadr · PCI 55–100 · oʻrtacha 78 |

Bu raqamlar oldindan oʻlchab qoʻyilgan. Ekranda boshqa natija chiqsa —
yozuvni toʻxtating va xabar bering, demak sozlamalar surilib ketgan.

---

## D. Tekshiruv roʻyxati — yuborishdan oldin

- [ ] Hech bir kadrda bildirishnoma yoki xatcho'plar paneli koʻrinmaydi
- [ ] Hech bir kadrda shaxsiy maʼlumot yoʻq
- [ ] Til almashtirish uch holatda ham yozib olingan
- [ ] Deduct zanjiri jadvali oʻqilarli darajada aniq
- [ ] Kamera balandligi 1.70 m dan boshlanadi (1.95 emas — u eski faraz)
- [ ] Sichqoncha harakati sekin va maqsadli
- [ ] Fayllar raqamlangan va nomlangan
- [ ] Yuklash bloki (18–21) yozilgan — bu blok tushib qolmasin
