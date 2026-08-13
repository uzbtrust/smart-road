# Claude Design — saytni tugatish va Vercel'ga topshirish

**Kim bajaradi:** Dostonbek, Claude Design'da
**Nima chiqadi:** eksport qilingan statik sayt → men Vercel'ga chiqaraman
**Nega shoshilinch:** professor sayt jonli bo'lmaguncha demo yoza olmaydi. Ya'ni
bu — butun qolgan ishning tiqilinch joyi.

⚠️ **Mavjud chatda davom eting.** Yangi chat ochmang — kontekst va tuzatishlar
tarixi yo'qoladi. "New design" faqat PDF deck uchun kerak bo'ladi.

---

## A. Har bir promptdan oldin

1. **Model Opus ekanini tekshiring.** Oldin Sonnet'ga o'tib qolgan edi.
2. **`SAYT_MATNI.md` ni biriktiring** — har safar emas, lekin agar model matnni
   o'zi to'qiy boshlasa, darrov qayta biriktiring.
3. **Bitta qoida hech qachon buzilmasin:** modelga yangi raqam o'ylab topishga
   ruxsat yo'q. Saytdagi har bir son `SAYT_MATNI.md` da bor.

---

## B. Prompt 1 — S3 va S4 (bosqichlar va demo)

```
Continue the marketing site with sections 3 and 4 from the attached copy.

S3 — HOW IT WORKS, four stages: Detect, Measure, Grade, Report.
Do not build this as four cards in a row with an icon on each. That is the
single most recognisable AI-generated layout and it makes the pipeline look
decorative. Build it as a sequence the eye follows: each stage takes the
output of the previous one as its input, and the reader should be able to see
that handoff. The interesting thing here is that stage 2 converts pixels into
square metres on the road plane — that conversion is the reason the score is
defensible, so give it more room than the other three.

S4 — DEMO. This section exists to be screen-recorded for the video pitch, so
it must hold up under a slow scroll at 1080p. Show: the detection overlay on
a real frame, the score card with the seven-band scale, and the deduct chain
table. The deduct chain is the most important object on the entire site —
density, deduct value, corrected deduct value, PCI, in that order, readable
at a glance. It is the proof that the number is not a black box.

RULES, unchanged
- Brand orange #F8A519 for emphasis only. Never as a large fill, and never
  inside a condition chart — the seven ASTM band colours own that space.
- Mono type is for values, never for labels.
- No left control rail. Nothing may read as a Streamlit app.
- Uzbek ʻ (U+02BB) keeps the sidebearing fix from the earlier pass. Check
  "oʻlchandi", "bogʻlanadi", "Yoʻl" in the new sections specifically.
```

---

## C. Prompt 2 — S5, S6, S7, S8

```
Now sections 5 to 8 from the attached copy.

S5 — VALIDATION. Two blocks. First, against the standard: the ASTM D6433
worked example publishes 51 and 49, we compute 51.4 and 48.6. Second, in the
field: Yangizamon street, 12 sections, the PCI table, whole street 51.4.
The table is real data, so set it as a data table a civil engineer would
trust — aligned decimals, no zebra striping, no rounded card around it.

S6 — HONEST LIMITS. Block cracking has 59 training examples. There is no
severity head. Frame overlap is not deduplicated. Design this as rigour, not
as a disclaimer buried at the bottom. A jury that sees a team state its own
weaknesses precisely trusts the rest of the numbers more. Same visual weight
as the validation section, not less.

S7 — TEAM. Four people with their actual roles, including the two who
measured PCI by hand in the field. The hand measurement is what makes the
validation section mean anything, so it should read as engineering work.

S8 — FOOTER. Links to GitHub, the live MVP, Hugging Face, Kaggle. Licences:
code MIT, weights AGPL-3.0 from Ultralytics.
```

---

## D. Prompt 3 — til almashtirish (bu eng nozik qismi)

Uch tillilik — ariza shartlaridan biri, va videoda ham ko'rsatiladi (yozuv
ro'yxatidagi 07-kadr). Shuning uchun alohida prompt bilan mustahkamlaymiz.

```
Now make the three languages work as a real, static-hostable mechanism.

This site will be deployed to Vercel as static files, so the switch cannot
depend on a server or a framework runtime. Requirements:

- All three languages ship in the page. The switch shows and hides, it does
  not fetch.
- The choice is reflected in the URL (?lang=ru), so a juror can be sent
  straight to one language and a reload keeps it.
- <html lang> updates with the switch — it changes how a screen reader and
  the browser treat the text.
- The switch is visible in the header without scrolling. It is evidence of a
  requirement being met, not a minor preference control.
- Uzbek is the default.
- Layout must not shift when switching. Russian runs about 15% longer than
  English and Uzbek longer still; headings must not reflow from two lines to
  three and push the section apart. Test the longest string in each block.
```

---

## E. Prompt 4 — eksport

Sayt to'liq bo'lgach:

```
Export this marketing site as a standalone static site I can deploy to Vercel:
plain HTML, CSS and JS, no build step, no framework runtime. Fonts must be
included rather than assumed — either self-hosted woff2 files or an explicit
stylesheet link, because a missing IBM Plex would silently fall back and the
Uzbek ʻ would break again. Images at the resolution they are displayed at,
not larger. Give me the whole thing as a folder I can download.
```

Yuklab olgach: papkani `deploy/site/` ga qo'ying va menga ayting. Qolganini
men qilaman.

---

## F. Topshirishdan oldin tekshiring

Bu ro'yxat qisqa, lekin har bandi haqiqiy xatoni ushlaydi.

- [ ] Uch tilda ham hech bir bo'lim bo'sh emas
- [ ] `oʻ` va `gʻ` hamma joyda to'g'ri chiqyapti — ayniqsa **yangi** bo'limlarda
- [ ] Til almashtirilganda maket sakramaydi
- [ ] Deduct zanjiri jadvali 1080p da o'qiladi (videoning eng muhim kadri)
- [ ] Yetti bandli shkala ranglari ASTM ranglari, brend to'q sarig'i emas
- [ ] Kamera balandligi biror joyda ko'rsatilgan bo'lsa — **1.70 m**, 1.95 emas
- [ ] Saytda `SAYT_MATNI.md` da yo'q birorta raqam yo'q
- [ ] Telefonda ochib ko'ring — hakam telefonda ochishi mumkin
- [ ] "So'zlarni va logotipni almashtirsam, bu boshqa kompaniyaning sayti
      bo'la oladimi?" — javob **yo'q** bo'lishi kerak

---

## G. Keyin nima bo'ladi

1. Siz eksportni `deploy/site/` ga qo'yasiz
2. Men Vercel'ga chiqaraman va jonli havolani beraman
3. Professor o'sha havola bilan demoni yozadi (`professor/1_DEMO_YOZUV.md`)
4. Yozuvdan video pitch chiqadi (`professor/2_VIDEO_PITCH.md`)
5. Saytdan skrinshotlar olinib PDF deck yasaladi (`professor/3_PDF_PITCH_DECK.md`)

Ya'ni 3, 4, 5-qadamlarning hammasi shu eksportni kutyapti.
