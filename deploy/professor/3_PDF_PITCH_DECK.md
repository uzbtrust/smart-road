# 3 — PDF Pitch Deck

**Kim bajaradi:** Claude Design'da yasaladi, Raximjon Soataliyev matnni tekshiradi
**Nima chiqadi:** bitta PDF fayl, ichida uch til ketma-ket (UZ → RU → EN)
**Qachon:** **sayt tayyor boʻlgandan keyin** — deckka saytdan skrinshotlar kiradi

---

## A. Avval: Claude Design PDF ni qanchalik yaxshi qila oladi

Halol javob, chunki reja shunga bogʻliq.

| Talab | Qila oladimi |
|---|---|
| Chiroyli maket, tipografiya, brend ranglari | ✅ **Ha.** Design system allaqachon qurilgan, deck oʻsha tokenlarni oladi |
| Haqiqiy rasmlar — sayt skrinshotlari, asfalt kadrlari, aniqlash qatlami | ✅ **Ha.** Rasmlar sahifaga joylashtiriladi |
| Diagrammalar, jadvallar, shkala, deduct zanjiri | ✅ **Ha.** Bular allaqachon design system komponentlari |
| Uch til | ✅ **Ha.** Matn tayyor |
| **Interaktivlik — bosiladigan tugmalar, animatsiya** | ❌ **Yoʻq.** PDF bunga qodir emas |

**Interaktivlik haqida aniq boʻlaylik.** Claude Design HTML yasaydi, PDF esa
oʻsha HTML ni chop etishdan chiqadi. Chop etilgandan keyin PDF — qogʻoz. Unda
tugma bosilmaydi, slayder surilmaydi, animatsiya ishlamaydi.

PDF da **ishlaydigan** yagona interaktiv narsa — **havolalar**. Shuning uchun
reja shunday: deck chiroyli va statik boʻladi, lekin har bir muhim slaydda
**jonli saytga va ishlayotgan MVP ga havola** turadi. Hakam bosadi va haqiqiy
mahsulotga tushadi. Bu — interaktivlikni taqlid qilishdan koʻra kuchliroq.

---

## B. Texnik talablar (Claude Design'ga aytiladi)

| Parametr | Qiymat | Nega |
|---|---|---|
| Sahifa oʻlchami | **297 × 167 mm** (16:9 landshaft) | Pitch deck slayd, A4 hujjat emas |
| Tema | **Yorugʻ** | Qorongʻi fon chop etishda katta fayl beradi va proyektorda yomon chiqadi |
| Shrift | IBM Plex Sans / Mono, **PDF ichiga singdirilgan** | Aks holda hakamning kompyuterida boshqa shrift bilan ochiladi |
| Rang | Toʻq sariq `#F8A519` faqat urgʻu uchun | Katta rangli maydonlar yoʻq |
| Sahifa uzilishi | Har slayd — alohida sahifa, `page-break-after: always` | |
| Rasm | Kamida 150 dpi | Skrinshot bulanib ketmasligi uchun |

**PDF ga aylantirish:** brauzerda `Cmd + P` → *Destination: Save as PDF* →
*Paper size: Custom 297×167mm* → *Margins: None* → **Background graphics: yoqilgan**
(bu belgilanmasa fon ranglari chop etilmaydi — eng koʻp uchraydigan xato).

---

## C. Slaydlar tuzilishi

Har til uchun **13 slayd**. Uch tilni ketma-ket qoʻyamiz, orasiga ajratuvchi
slayd. Jami ~41 sahifa. Formada bitta yuklash joyi bor, shuning uchun bitta fayl.

| № | Slayd | Ichida nima |
|---|---|---|
| 1 | **Muqova** | Logotip, "Smart Road", bir jumlalik taʼrif, jonli sayt havolasi |
| 2 | **Muammo** | Bugun yoʻl holatini odam lenta bilan oʻlchaydi. 1 810 m — bir necha kunlik ish |
| 3 | **Hamma nima qiladi** | Nuqsonni sanaydi. Sanoq savolga javob bermaydi |
| 4 | ⭐ **Asosiy topilma** | S7 vs S11 taqqoslash. Ellik barobar zichlik farqi, toʻrt barobar zarar farqi. Ikki usul ikki xil "eng yomon boʻlak" beradi |
| 5 | **Yechim — 4 bosqich** | Aniqlash → Oʻlchash → Baholash → Hisobot |
| 6 | **Mahsulot** | Saytdan skrinshot: hero + aniqlash qatlami |
| 7 | **Mahsulot** | Ilovadan skrinshot: baho kartasi va yetti bandli shkala |
| 8 | **Raqam yashirin emas** | Deduct zanjiri jadvali skrinshoti |
| 9 | **Tekshiruv — standart** | ASTM namunaviy misoli: nashr etilgan 51/49, bizda 51.4/48.6 |
| 10 | **Tekshiruv — dala** | Yangizamon 12 boʻlagi, PCI jadvali, butun koʻcha 51.4 |
| 11 | **Model va maʼlumot** | mAP50 0.657, 113 648 quti, 4 ta ochiq manba, 181 test |
| 12 | **Halol cheklovlar** | Bloksimon yoriq 59 namuna, severity head yoʻq, kadrlararo takror |
| 13 | **Jamoa va havolalar** | 4 kishi, GitHub / Hugging Face / Kaggle / jonli sayt |

**Matn manbai:** har bir slaydning matni `SAYT_MATNI.md` da tayyor — slaydlar
saytning bo'limlariga bir-birga mos keladi (S1→2, S2→4, S3→5, S5→9,10,11,
S6→12, S7→13).

---

## D. Claude Design'ga beriladigan prompt

Sayt tugagach, **"New design"** tugmasi orqali yangi dizayn oching (saytning
oʻzida davom ettirmang) va shuni yozing:

```
Build a pitch deck as a print-ready PDF using this design system.

FORMAT — this is a slide deck, not a document.
Page size exactly 297 × 167 mm, landscape (16:9). Every slide is its own page:
page-break-after: always, no content ever splits across a page. Zero page margin;
the design owns the full bleed. Light theme throughout — a dark deck prints to a
huge file and dies on a projector. Embed IBM Plex Sans and Mono rather than
linking them, so the PDF renders identically on a jury's machine.

CONTENT — 13 slides per language, three languages in sequence: Uzbek, then
Russian, then English, with a single divider slide between languages. The copy is
already written and attached; place it, do not rewrite it.

1  Cover — logo, name, one-sentence definition, link to the live site
2  The problem — road condition is measured by hand today; 1,810 m took days
3  What everyone else does — counting defects; counting does not answer the question
4  THE FINDING — S7 against S11. Fifty times the density difference, four times
   the damage in the other direction, and the two methods disagree about which
   section is worst. This is the slide the jury must remember: give it the most
   design attention in the whole deck, as a data figure, not as bullets.
5  The solution — four stages: Detect, Measure, Grade, Report
6  The product — screenshot from the site: hero and detection overlay
7  The product — screenshot from the app: score card and the seven-band scale
8  The number is not hidden — screenshot of the deduct chain table
9  Validation, the standard — ASTM worked example: published 51 / 49, ours 51.4 / 48.6
10 Validation, the field — Yangizamon, 12 sections, the PCI table, street 51.4
11 Model and data — mAP50 0.657, 113,648 boxes, four public sources, 181 tests
12 Honest limits — block cracking has 59 training examples, no severity head,
    frame overlap not deduplicated. Design this as rigour, not as small print.
13 Team and links — four people; GitHub, Hugging Face, Kaggle, the live site

INTERACTIVITY — a PDF cannot have any, so do not attempt it. What it can have is
links: put a real, clickable link to the live site and to the working MVP on the
cover, on slides 6, 7 and 8, and on slide 13. Style them as links a reader
notices, not as fake buttons.

RULES
- No bullet-point slides with a title and four dashes. Every slide is a figure,
  a table, a screenshot or one large statement.
- No stock imagery, no icons as decoration. The screenshots and the road
  photographs are the images.
- Brand orange for emphasis only, never as a large fill, and never inside a
  condition chart.
- Every number on a slide is one that appears in the copy. Nothing new.

Give me slides 1 to 4 in Uzbek first, at full fidelity, before the rest.
```

---

## E. Tekshiruv roʻyxati

- [ ] PDF 16:9, har slayd alohida sahifa
- [ ] Shriftlar PDF ichiga singdirilgan (`Cmd+D` → *Fonts* boʻlimida tekshiriladi)
- [ ] Fon ranglari chop etilgan (*Background graphics* yoqilgan edi)
- [ ] Uch til ham toʻliq, ajratuvchi slaydlar bilan
- [ ] Havolalar bosiladi va toʻgʻri manzilga boradi
- [ ] Skrinshotlar aniq, bulanmagan
- [ ] 4-slayd (asosiy topilma) deckdagi eng kuchli sahifa
- [ ] Fayl hajmi 20 MB dan kam — yuklash chegarasi boʻlishi mumkin
- [ ] Fayl nomi: `smart_road_pitch_deck.pdf`
