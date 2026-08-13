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

### Blok 2 — Ilova, fotosurat rejimi (2 daqiqa atrofida)

| № | Nima yoziladi | Davomiyligi | Izoh |
|---|---|---|---|
| 08 | Namuna rasm tanlanadi, natija chiqadi | 15 s | Kutish vaqtini kesmang — halol koʻrinsin |
| 09 | Aniqlash qatlamiga yaqinlashish | 8 s | Ramkalar va sinf nomlari oʻqilsin |
| 10 | Baho kartasi va yetti bandli shkala | 8 s | |
| 11 | **Deduct zanjiri jadvali** | 12 s | Eng muhim kadr. Zichlik → chegirma → tuzatilgan → PCI |
| 12 | **Jiddiylik slayderi**: past → oʻrta → yuqori | 12 s | Uch qiymat oʻzgarishini koʻrsating |
| 13 | **Kamera balandligi**: 1.70 → 2.20 → 1.70 | 12 s | PCI siljishini koʻrsating. Bu — halollik dalili |
| 14 | **Plitkali inferens**: yoqilgan → oʻchirilgan → yoqilgan | 15 s | Aniqlashlar yoʻqolib qaytishi koʻrinsin |

### Blok 3 — Ilova, video rejimi (1 daqiqa atrofida)

| № | Nima yoziladi | Davomiyligi | Izoh |
|---|---|---|---|
| 15 | 15 soniyalik klip tanlanadi, tahlil boshlanadi | 20 s | Jarayonni kesmang |
| 16 | Holat tasmasi toʻliq chiqadi | 10 s | Yashildan qizilgacha oʻtish koʻrinsin |
| 17 | Eng yomon kadr bosiladi | 10 s | |

---

## B2. Qaysi namunalarni tanlash kerak — aniq roʻyxat

Ilovaning **Sample** roʻyxatidan aynan shu uchtasini tanlang. Ular saytda
koʻrsatilgan kadrlarning oʻzi, ya'ni video bilan sayt bir xil rasmni koʻrsatadi
va hakam ikkisini bogʻlay oladi.

| Kadr | Roʻyxatda qanday koʻrinadi | Nega aynan shu |
|---|---|---|
| **Fotosurat 1** | `attain tehran  Attain SMP WS v2 000795` | Saytdagi ikkinchi rasm shu. 1024×576 |
| **Fotosurat 2** | `yangizamon forward 160s` | Saytdagi asosiy (hero) kadr shu. Toshkent, 1920×1080 |
| **Video** | `yangizamon 15s` | 15 soniya, tahlil ~45–60 s davom etadi |

Fayllar repoda: `samples/` papkasida. Ularni alohida yuklab olish **shart emas** —
ilovaning oʻzida tayyor turibdi, roʻyxatdan tanlansa boʻldi.

Saytdagi kadr esa `reports/demo/tiled_4k_fwd_160s.jpg` — bu `yangizamon
forward 160s` ning aniqlangan (ramkalar chizilgan) varianti. Ya'ni videoda
tomoshabin saytdagi rasmning qanday hosil boʻlganini koʻradi.

---

## C. Yozib boʻlgach — montajchiga nima beriladi

1. **Barcha `.mov` fayllar** — kesilmagan, siqilmagan
2. **Bu fayl** — shot list bilan
3. `2_VIDEO_PITCH.md` — u yerda qaysi kadr qaysi jumla ostida turishi yozilgan
4. **Logotip**: `Logo/SVG/` papkasi (vektor — istalgan oʻlchamda aniq)
5. **Brend ranglari:** toʻq sariq `#F8A519`, koʻmir `#3A3A3C`

---

## D. Tekshiruv roʻyxati — yuborishdan oldin

- [ ] Hech bir kadrda bildirishnoma yoki xatcho'plar paneli koʻrinmaydi
- [ ] Hech bir kadrda shaxsiy maʼlumot yoʻq
- [ ] Til almashtirish uch holatda ham yozib olingan
- [ ] Deduct zanjiri jadvali oʻqilarli darajada aniq
- [ ] Kamera balandligi 1.70 m dan boshlanadi (1.95 emas — u eski faraz)
- [ ] Sichqoncha harakati sekin va maqsadli
- [ ] Fayllar raqamlangan va nomlangan
