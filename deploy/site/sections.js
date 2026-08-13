/* Smart Road — static site, part 2: the eight sections and the boot sequence.

   Copy is placed from copy.js verbatim, in all three languages. Nothing here
   writes or edits a string, and no figure is computed that is not in the copy
   or in data.js. */
(function (w) {
  "use strict";
  var S = w.SR, el = S.el, svg = S.svg;

  /* ── S0 · chrome ──
     Nav entry i → the section it points at, from the copy's own numbering:
     Home S1 · How it works S3 · Validation S5 · Limits S6 · Team S7.
     BUILT lists the sections that exist; an entry whose section is missing
     renders as plain text, never as a link that goes nowhere. */
  var NAV_TARGETS = ["s1", "s3", "s5", "s6", "s7"];
  var BUILT = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"];

  function header(c, state, set) {
    return el("header", { class: "site-head" },
      el("div", { class: "site-head-in" },
        el("a", { href: "#s1", style: { borderBottom: "none", display: "flex", alignItems: "center", flex: "0 0 auto" } },
          el("img", { src: state.theme === "dark" ? "assets/logo-lockup-on-charcoal.svg" : "assets/logo-lockup.svg", alt: "Smart Road", style: { height: 22, display: "block" } })),
        el("nav", { class: "site-nav" }, c.nav.map(function (n, i) {
          var id = NAV_TARGETS[i];
          if (BUILT.indexOf(id) < 0) return el("span", { style: { fontSize: "var(--t-ui)", whiteSpace: "nowrap", color: "var(--ink-3)", opacity: 0.55 } }, n);
          return el("a", { href: "#" + id, "aria-current": i === 0 ? "true" : null }, n);
        })),
        el("div", { class: "head-controls" },
          S.segmented([{ value: "dark", label: c.chrome.theme[0] }, { value: "light", label: c.chrome.theme[1] }], state.theme, function (v) { set({ theme: v }); }, "Theme"),
          S.langSwitcher(state.lang, function (v) { set({ lang: v }); }),
          S.button(c.cta, "sm", function () { w.open(w.SR_MVP_URL, "_blank", "noopener"); }))));
  }

  /* ── S1 · hero ──
     Asymmetric on purpose: the text column sits on the page grid and the survey
     frame runs off the right edge of the viewport. */
  function hero(c) {
    var s = c.s1, D = w.SR_DATA;
    var strip = el("div", { style: { position: "absolute", left: 0, right: 0, bottom: 0, display: "flex", flexWrap: "wrap", alignItems: "center", gap: "var(--sp-5)", padding: "10px var(--sp-6)", background: "linear-gradient(to top, rgba(10,10,9,.88), rgba(10,10,9,.62) 60%, transparent)" } },
      el("span", { style: { fontSize: "var(--t-small)", color: "#EDEDEA", whiteSpace: "nowrap" } }, s.measure[0]),
      el("span", { style: { width: 1, height: 14, background: "rgba(237,237,234,.3)" } }),
      el("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--t-micro)", letterSpacing: "0.06em", color: "rgba(237,237,234,.7)" } }, s.measure[1]),
      el("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--t-h4)", fontWeight: "var(--fw-semibold)", color: "#fff", fontVariantNumeric: "tabular-nums", letterSpacing: "-0.02em" } }, s.measure[2]),
      el("span", { style: { display: "inline-flex", alignItems: "center", gap: 6, padding: "2px 8px", borderRadius: "var(--r-1)", background: "var(--band-poor)", color: "var(--band-poor-ink)", fontSize: "var(--t-micro)", fontWeight: "var(--fw-semibold)" } }, s.measure[3]));

    var fig = el("figure", { style: { margin: 0, minWidth: 0 } },
      el("div", { style: { position: "relative", borderTopLeftRadius: "var(--r-4)", borderBottomLeftRadius: "var(--r-4)", overflow: "hidden" } },
        S.detectionOverlay("assets/hero-yangizamon.jpg", { y: 44, h: 56 }, D.heroBoxes, 0), strip),
      S.caption(1, s.caption, "reports/demo/tiled_4k_fwd_160s.jpg"));
    fig.lastChild.style.paddingRight = "var(--sp-8)";

    return el("section", { id: "s1", class: "g-hero" },
      el("div", {},
        el("h1", { style: { fontSize: "var(--t-display)", lineHeight: 1.03, letterSpacing: "-0.028em", margin: "0 0 var(--sp-7)", textWrap: "balance" } }, s.h1),
        el("p", { style: { fontSize: "var(--t-lede)", color: "var(--ink-2)", lineHeight: 1.5, margin: "0 0 var(--sp-8)", maxWidth: "42ch" } }, s.sub),
        el("p", { style: { margin: "0 0 var(--sp-8)", paddingLeft: "var(--sp-5)", borderLeft: "2px solid var(--line-strong)", fontSize: "var(--t-small)", color: "var(--ink-2)", lineHeight: "var(--lh-body)", maxWidth: "44ch" } },
          s.trust[0], el("span", { style: { fontFamily: "var(--font-mono)", fontWeight: "var(--fw-semibold)", color: "var(--ink-1)", fontVariantNumeric: "tabular-nums" } }, s.trust[1]),
          s.trust[2], el("span", { style: { fontFamily: "var(--font-mono)", fontWeight: "var(--fw-semibold)", color: "var(--ink-1)", fontVariantNumeric: "tabular-nums" } }, s.trust[3]), s.trust[4]),
        S.button(s.cta, "lg", function () { w.open(w.SR_MVP_URL, "_blank", "noopener"); })),
      fig);
  }

  /* ── S2 · the reversal ──
     Two ranking methods disagree about which section of the street is worst, and
     that disagreement is the site's argument — so it is drawn twice rather than
     asserted: the two sections at one shared scale, then all twelve ranked both
     ways with the crossing lines in ink. Brand orange appears in neither. */
  var DENSITY_MAX = 40, DEDUCT_MAX = 70;

  function quantity(labelText, printed, value, max, colour, lead) {
    return el("div", {},
      el("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "var(--sp-4)", marginBottom: 5 } },
        S.label(labelText),
        el("span", { style: { fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontSize: lead ? "var(--t-h4)" : "var(--t-ui)", fontWeight: lead ? "var(--fw-semibold)" : "var(--fw-regular)", color: lead ? "var(--ink-1)" : "var(--ink-2)" } }, printed)),
      el("div", { style: { height: 10, background: "var(--track)", borderRadius: 1, overflow: "hidden" } },
        el("div", { style: { width: Math.max(0.4, (value / max) * 100) + "%", height: "100%", background: colour } })));
  }

  function sectionPanel(p, labels) {
    return el("div", { style: { background: "var(--surface-figure)", border: "1px solid var(--line-1)", borderRadius: "var(--r-4)", padding: "var(--sp-6)" } },
      el("div", { style: { display: "flex", alignItems: "baseline", gap: "var(--sp-4)", marginBottom: "var(--sp-6)" } },
        el("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--t-h2)", fontWeight: "var(--fw-semibold)", letterSpacing: "-0.02em", color: "var(--ink-1)" } }, p.code),
        el("span", { style: { fontSize: "var(--t-small)", color: "var(--ink-2)", lineHeight: "var(--lh-ui)" } }, p.distress)),
      el("div", { style: { display: "grid", gap: "var(--sp-6)" } },
        quantity(labels.density, p.density, p.densityValue, DENSITY_MAX, "var(--data-2)", p.densityLead),
        quantity(labels.deduct, p.deduct, p.deductValue, DEDUCT_MAX, "var(--data-1)", p.deductLead)));
  }

  function rankReversal(lang, c) {
    var secs = w.SR_DATA.sections;
    var byCdl = secs.slice().sort(function (a, b) { return b.cdl - a.cdl; });
    var byPci = secs.slice().sort(function (a, b) { return a.pci - b.pci; });
    var rank = function (list, s) { return list.findIndex(function (x) { return x.s === s.s; }); };
    var W = 760, ROW = 30, TOP = 34, H = TOP + secs.length * ROW + 8, xL = 214, xR = W - 214;
    var y = function (i) { return TOP + i * ROW + ROW / 2; };
    var focus = { S11: "var(--data-2)", S7: "var(--data-1)" };
    var n = function (v, d) { return w.srNum(v, lang, d); };
    var tick = { fontFamily: "var(--font-mono)", fontSize: 11, fontVariantNumeric: "tabular-nums" };
    var head = { fontFamily: "var(--font-sans)", fontSize: 10, fontWeight: 600, letterSpacing: "0.11em", textTransform: "uppercase", fill: "var(--ink-3)" };

    var g = svg("svg", { viewBox: "0 0 " + W + " " + (H + 14), style: { width: "100%", height: "auto", display: "block", overflow: "visible" }, role: "img", "aria-label": c.axisLeft + " / " + c.axisRight },
      svg("text", { x: xL, y: 16, "text-anchor": "end", style: head }, c.axisLeft),
      svg("text", { x: xR, y: 16, "text-anchor": "start", style: head }, c.axisRight),
      svg("line", { x1: xL, x2: xL, y1: TOP - 4, y2: H - 4, stroke: "var(--line-2)" }),
      svg("line", { x1: xR, x2: xR, y1: TOP - 4, y2: H - 4, stroke: "var(--line-2)" }));

    secs.forEach(function (s) {
      var i = rank(byCdl, s), j = rank(byPci, s), f = focus[s.s], mid = (xL + xR) / 2;
      g.appendChild(svg("path", { d: "M" + xL + " " + y(i) + " C" + mid + " " + y(i) + " " + mid + " " + y(j) + " " + xR + " " + y(j), fill: "none", stroke: f || "var(--line-2)", "stroke-width": f ? 2 : 1, opacity: f ? 1 : 0.5 }));
    });
    byCdl.forEach(function (s, i) {
      var f = focus[s.s];
      g.appendChild(svg("circle", { cx: xL, cy: y(i), r: f ? 3.5 : 2, fill: f || "var(--line-strong)" }));
      g.appendChild(svg("text", { x: xL - 10, y: y(i), "text-anchor": "end", "dominant-baseline": "middle", style: Object.assign({}, tick, { fontSize: 12, fontWeight: f ? 600 : 400, fill: f ? "var(--ink-1)" : "var(--ink-3)" }) }, s.s));
      g.appendChild(svg("text", { x: xL - 44, y: y(i), "text-anchor": "end", "dominant-baseline": "middle", style: Object.assign({}, tick, { fill: f ? "var(--ink-2)" : "var(--ink-3)", opacity: f ? 1 : 0.7 }) }, n(s.cdl, 2)));
    });
    byPci.forEach(function (s, j) {
      var f = focus[s.s];
      g.appendChild(svg("circle", { cx: xR, cy: y(j), r: f ? 3.5 : 2, fill: f || "var(--line-strong)" }));
      g.appendChild(svg("text", { x: xR + 10, y: y(j), "text-anchor": "start", "dominant-baseline": "middle", style: Object.assign({}, tick, { fontSize: 12, fontWeight: f ? 600 : 400, fill: f ? "var(--ink-1)" : "var(--ink-3)" }) }, s.s));
      g.appendChild(svg("text", { x: xR + 44, y: y(j), "text-anchor": "start", "dominant-baseline": "middle", style: Object.assign({}, tick, { fill: f ? "var(--ink-2)" : "var(--ink-3)", opacity: f ? 1 : 0.7 }) }, n(s.pci, 1)));
    });
    g.appendChild(svg("text", { x: (xL + xR) / 2, y: H + 8, "text-anchor": "middle", style: head }, c.axisNote));
    return g;
  }

  function argument(c) {
    var s = c.s2, labels = { density: s.densityLabel, deduct: s.deductLabel };
    return el("section", { id: "s2", class: "plane-raised" }, el("div", { class: "wrap" },
      el("div", { class: "g-75 g-75-end", style: { marginBottom: "var(--sp-10)" } },
        el("h2", { style: { fontSize: "var(--t-h1)", letterSpacing: "-0.024em", lineHeight: 1.1, margin: 0, textWrap: "balance" } }, s.h2),
        el("p", { style: { margin: 0, fontSize: "var(--t-small)", color: "var(--ink-2)", lineHeight: "var(--lh-body)" } }, s.intro)),
      el("div", { class: "g-compare" },
        sectionPanel({ code: s.left.code, distress: s.left.distress, density: s.left.density, densityValue: 35.2, densityLead: true, deduct: s.left.deduct, deductValue: 16.9 }, labels),
        el("div", { class: "rot", style: { display: "flex", flexDirection: "column", alignItems: "center", gap: 6, color: "var(--ink-3)" } },
          el("span", { style: { width: 1, height: 34, background: "var(--line-2)" } }),
          el("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--t-micro)", letterSpacing: "0.04em" } }, "47×"),
          el("span", { style: { width: 1, height: 34, background: "var(--line-2)" } })),
        sectionPanel({ code: s.right.code, distress: s.right.distress, density: s.right.density, densityValue: 0.745, deduct: s.right.deduct, deductValue: 62.6, deductLead: true }, labels)),
      el("p", { style: { margin: "var(--sp-8) 0 0", fontSize: "var(--t-lede)", lineHeight: 1.45, letterSpacing: "-0.008em", color: "var(--ink-2)", maxWidth: "62ch" } },
        s.middle[0], el("strong", { style: { color: "var(--ink-1)", fontWeight: "var(--fw-semibold)" } }, s.middle[1]),
        s.middle[2], el("strong", { style: { color: "var(--ink-1)", fontWeight: "var(--fw-semibold)" } }, s.middle[3]), s.middle[4]),
      el("div", { style: { marginTop: "var(--sp-11)", background: "var(--surface-figure)", border: "1px solid var(--line-1)", borderRadius: "var(--r-4)", padding: "var(--sp-8) var(--sp-9) var(--sp-9)" } },
        rankReversal(c.__lang, s)),
      el("div", { class: "g-75 g-75-start", style: { marginTop: "var(--sp-7)" } },
        el("p", { style: { display: "flex", gap: "var(--sp-4)", margin: 0, fontSize: "var(--t-caption)", lineHeight: "var(--lh-caption)", color: "var(--ink-2)" } },
          S.figMark(2), el("span", {}, s.figCaption, el("span", { style: { fontFamily: "var(--font-mono)", color: "var(--ink-3)" } }, " DATA/docs/YANGIZAMON_PCI.md §3"))),
        el("table", { style: { borderTop: "1px solid var(--line-strong)", width: "100%", borderCollapse: "collapse", fontSize: "var(--t-small)" } },
          el("thead", {}, el("tr", {},
            el("th", { style: { borderBottom: "1px solid var(--line-1)" } }),
            el("th", { colspan: "2", style: { textAlign: "right", borderBottom: "1px solid var(--line-1)", padding: "var(--sp-3) var(--sp-4)", color: "var(--ink-2)", fontSize: "var(--t-caption)" } }, s.resultHead))),
          el("tbody", {}, s.resultRows.map(function (r) {
            return el("tr", {},
              el("td", { style: { color: "var(--ink-2)", padding: "var(--sp-3) var(--sp-4)", borderBottom: "1px solid var(--line-1)" } }, r[0]),
              el("td", { style: { textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: "var(--fw-semibold)", color: "var(--ink-1)", fontSize: "var(--t-ui)", padding: "var(--sp-3) var(--sp-4)", borderBottom: "1px solid var(--line-1)" } }, r[1]),
              el("td", { style: { textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--ink-3)", whiteSpace: "nowrap", padding: "var(--sp-3) var(--sp-4)", borderBottom: "1px solid var(--line-1)" } }, r[2]));
          })))),
      el("div", { class: "g-75 g-75-start", style: { marginTop: "var(--sp-10)", paddingTop: "var(--sp-8)", borderTop: "1px solid var(--line-1)" } },
        el("p", { style: { margin: 0, fontSize: "var(--t-h3)", lineHeight: 1.3, letterSpacing: "-0.014em", color: "var(--ink-1)", textWrap: "pretty" } }, s.conclusion),
        S.callout("note", "CDL", s.note))));
  }

  /* ── S3 · the pipeline ──
     A sequence down one rule, not four cards. Between each pair sits the thing
     that actually passes to the next stage, placed ON the rule, so the eye
     follows one line from frame to grade. Stage 2 carries the extra room: it is
     the conversion the whole defensibility rests on. */
  function handoff(text) {
    return el("div", { style: { display: "grid", gridTemplateColumns: "44px minmax(0,1fr)", columnGap: "var(--sp-7)" } },
      el("div", { style: { position: "relative", display: "flex", justifyContent: "center" } },
        el("span", { style: { width: 1, background: "var(--line-2)", height: 52 } }),
        el("span", { style: { position: "absolute", top: 20, left: "50%", transform: "translateX(-50%)", width: 7, height: 7, borderRadius: "50%", background: "var(--plane)", border: "1px solid var(--line-strong)" } })),
      el("div", { style: { display: "flex", alignItems: "center", height: 52 } },
        el("span", { style: { fontSize: "var(--t-caption)", color: "var(--ink-3)" } },
          el("span", { style: { fontFamily: "var(--font-mono)", marginRight: 8 } }, "↓"), text)));
  }

  function stage(st, wide, extra) {
    return el("div", { style: { display: "grid", gridTemplateColumns: "44px minmax(0,1fr)", columnGap: "var(--sp-7)" } },
      el("div", { style: { display: "flex", flexDirection: "column", alignItems: "center" } },
        el("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--t-h2)", fontWeight: "var(--fw-semibold)", lineHeight: 1, letterSpacing: "-0.02em", color: "var(--ink-1)", fontVariantNumeric: "tabular-nums" } }, st.n),
        el("span", { style: { width: 1, flex: 1, background: "var(--line-2)", marginTop: 10 } })),
      el("div", { style: { paddingBottom: "var(--sp-2)" } },
        el("h3", { style: { fontSize: "var(--t-h3)", letterSpacing: "-0.014em", margin: "0 0 var(--sp-4)" } }, st.name),
        el("p", { style: { margin: "0 0 var(--sp-4)", fontSize: wide ? "var(--t-body)" : "var(--t-small)", color: "var(--ink-2)", lineHeight: "var(--lh-body)", maxWidth: wide ? "68ch" : "62ch" } }, st.body),
        el("p", { style: { margin: 0, fontSize: "var(--t-caption)", color: "var(--ink-3)", lineHeight: "var(--lh-caption)", fontStyle: "italic" } }, S.rich(st.note)),
        extra));
  }

  function pipeline(c) {
    var s = c.s3;
    var stage2extra = el("div", { class: "g-stage2", style: { marginTop: "var(--sp-7)" } },
      el("figure", { style: { margin: 0, minWidth: 0 } },
        S.detectionOverlay("assets/frame-tehran.jpg", { y: 45, h: 55 }, []),
        el("figcaption", { style: { marginTop: "var(--sp-3)", fontSize: "var(--t-caption)", color: "var(--ink-3)", lineHeight: "var(--lh-caption)" } }, s.figCaption)),
      el("dl", { style: { margin: 0, borderTop: "1px solid var(--line-strong)" } },
        el("dt", { style: Object.assign({}, S.LABEL, { padding: "var(--sp-4) 0 var(--sp-3)" }) }, s.inputsLabel),
        s.inputs.map(function (name, i) {
          return el("dd", { style: { margin: 0, display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "var(--sp-4)", padding: "7px 0", borderTop: "1px solid var(--line-1)", fontSize: "var(--t-small)", color: "var(--ink-2)" } },
            el("span", {}, name),
            i === 0 ? el("span", { style: { fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--ink-1)", fontWeight: "var(--fw-semibold)" } }, s.inputsValue) : null);
        })));

    return el("section", { id: "s3" }, el("div", { class: "wrap" },
      el("h2", { style: { fontSize: "var(--t-h1)", letterSpacing: "-0.024em", lineHeight: 1.1, margin: "0 0 var(--sp-10)", maxWidth: "22ch" } }, s.h2),
      stage(s.stages[0]), handoff(s.handoff[0]),
      stage(s.stages[1], true, stage2extra), handoff(s.handoff[1]),
      stage(s.stages[2]), handoff(s.handoff[2]),
      stage(s.stages[3])));
  }

  /* ── S4 · the demo ──
     Filmed for the video pitch, so it is sized for a slow scroll at 1080p: the
     deduct chain runs at the widest measure the grid allows and its type scale
     is raised through token overrides, so it scales as one object. */
  function demo(c) {
    var s = c.s4, D = w.SR_DATA, f = D.frame;
    var chain = el("div", { style: { marginTop: "var(--sp-12)", "--t-small": "15.5px", "--t-caption": "13.5px", "--t-micro": "12.5px" } });
    chain.style.setProperty("--t-small", "15.5px");
    chain.style.setProperty("--t-caption", "13.5px");
    chain.style.setProperty("--t-micro", "12.5px");
    chain.appendChild(S.deductChain(f, c.__lang));
    chain.appendChild(el("p", { style: { display: "flex", gap: "var(--sp-4)", margin: "var(--sp-6) 0 0", fontSize: "var(--t-caption)", lineHeight: "var(--lh-caption)", color: "var(--ink-2)", maxWidth: "var(--measure-note)" } },
      S.figMark(4), el("span", {}, s.chainCaption)));

    return el("section", { id: "s4", class: "plane-raised" }, el("div", { class: "wrap" },
      el("div", { class: "g-75 g-75-end", style: { marginBottom: "var(--sp-9)" } },
        el("h2", { style: { fontSize: "var(--t-h1)", letterSpacing: "-0.024em", lineHeight: 1.1, margin: 0 } }, s.h2),
        el("p", { style: { margin: 0, fontSize: "var(--t-small)", color: "var(--ink-2)", lineHeight: "var(--lh-body)" } }, s.sub)),
      el("div", { class: "g-75 g-75-start" },
        S.videoBlock("assets/demo-poster.jpg", null, s.playLabel, "smart_road_demo.mp4"),
        el("div", {},
          el("h3", { style: Object.assign({}, S.LABEL, { margin: "0 0 var(--sp-6)" }) }, s.noticeHead),
          el("ol", { style: { margin: 0, padding: 0, listStyle: "none", display: "grid", gap: "var(--sp-6)" } },
            s.notice.map(function (parts, i) {
              return el("li", { style: { display: "grid", gridTemplateColumns: "26px minmax(0,1fr)", gap: "var(--sp-4)", alignItems: "start" } },
                el("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--t-small)", color: "var(--ink-3)", fontVariantNumeric: "tabular-nums", paddingTop: 2, borderTop: "2px solid var(--line-strong)" } }, String(i + 1)),
                el("span", { style: { fontSize: "var(--t-small)", color: "var(--ink-2)", lineHeight: "var(--lh-body)" } }, S.rich(parts)));
            })))),
      el("div", { class: "g-side", style: { marginTop: "var(--sp-12)" } },
        el("figure", { style: { margin: 0, minWidth: 0 } },
          S.detectionOverlay("assets/frame-tehran.jpg", f.roi, f.boxes),
          S.caption(3, s.overlayCaption),
          el("div", { style: { marginTop: "var(--sp-6)" } }, S.detectionLegend(c.__lang, f.boxes.map(function (b) { return b.cls; }), 2))),
        S.scoreCard(f.pci, c.__lang, 1)),
      chain));
  }

  /* ── S5 · validation ──
     A spec sheet, then the field survey set as a data table an engineer can
     trust: ruled top and bottom, decimals aligned in a mono column, no zebra
     striping and no card. The band is a 2 px rule under each value — twelve of
     them abutting read as a condition profile along the street. */
  function surveyTable(lang, sectionLabel, capText) {
    var secs = w.SR_DATA.sections;
    var worst = secs.reduce(function (a, b) { return b.pci < a.pci ? b : a; }, secs[0]);
    var fig = el("figure", { style: { margin: 0 } },
      el("div", { class: "survey-scroll" },
        el("table", { style: { width: "100%", borderCollapse: "collapse", borderTop: "1px solid var(--line-strong)", borderBottom: "1px solid var(--line-strong)" } },
          el("caption", { style: Object.assign({}, S.LABEL, { captionSide: "top", textAlign: "left", paddingBottom: "var(--sp-4)" }) }, sectionLabel),
          el("tbody", {},
            el("tr", {}, secs.map(function (s) {
              return el("th", { scope: "col", style: { padding: "var(--sp-3) 0 5px", textAlign: "right", borderBottom: "1px solid var(--line-1)", fontFamily: "var(--font-mono)", fontSize: "var(--t-caption)", fontWeight: "var(--fw-regular)", letterSpacing: 0, color: s.s === worst.s ? "var(--ink-1)" : "var(--ink-3)" } }, s.s);
            })),
            el("tr", {}, secs.map(function (s) {
              return el("td", { style: { padding: "var(--sp-4) 0 0", textAlign: "right", verticalAlign: "bottom", border: "none" } },
                el("span", { style: { display: "block", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontSize: s.s === worst.s ? "var(--t-lede)" : "var(--t-ui)", fontWeight: s.s === worst.s ? "var(--fw-semibold)" : "var(--fw-regular)", color: s.s === worst.s ? "var(--ink-1)" : "var(--ink-2)", paddingBottom: 6 } }, w.srNum(s.pci, lang, 1)),
                el("span", { style: { display: "block", height: 2, background: "var(--band-" + w.srBand(s.pci) + ")", marginBottom: "var(--sp-4)" } }));
            }))))),
      S.caption(5, capText, "DATA/docs/YANGIZAMON_PCI.md §2"));
    fig.lastChild.style.marginTop = "var(--sp-6)";
    return fig;
  }

  function validation(c) {
    var s = c.s5;
    return el("section", { id: "s5" }, el("div", { class: "wrap" },
      el("h2", { style: { fontSize: "var(--t-h1)", letterSpacing: "-0.024em", lineHeight: 1.1, margin: "0 0 var(--sp-9)", maxWidth: "20ch" } }, s.h2),
      el("div", { class: "g-3" }, s.tiles.map(S.metricTile)),
      el("div", { class: "g-75 g-75-end", style: { marginTop: "var(--sp-12)", marginBottom: "var(--sp-8)" } },
        el("h3", { style: { fontSize: "var(--t-h2)", letterSpacing: "-0.018em", margin: 0 } }, s.h3),
        el("p", { style: { margin: 0, fontSize: "var(--t-small)", color: "var(--ink-2)", lineHeight: "var(--lh-body)" } }, s.text)),
      surveyTable(c.__lang, s.sectionLabel, s.tableCaption),
      el("div", { class: "g-75 g-75-start", style: { marginTop: "var(--sp-9)" } },
        el("p", { style: { margin: 0, fontSize: "var(--t-h3)", lineHeight: 1.32, letterSpacing: "-0.014em", color: "var(--ink-1)", textWrap: "pretty" } }, S.rich(s.whole)),
        S.callout("note", s.alsoLabel, S.rich(s.also)))));
  }

  /* ── S6 · the limits ──
     Same heading scale, same measure and the same plane treatment as S5. This
     section is the reason the numbers above it are believable, so it is never
     set smaller or pushed to the end. */
  function limits(c) {
    var s = c.s6;
    return el("section", { id: "s6", class: "plane-raised" }, el("div", { class: "wrap" },
      el("div", { class: "g-75 g-75-end", style: { marginBottom: "var(--sp-10)" } },
        el("h2", { style: { fontSize: "var(--t-h1)", letterSpacing: "-0.024em", lineHeight: 1.1, margin: 0 } }, s.h2),
        el("p", { style: { margin: 0, fontSize: "var(--t-small)", color: "var(--ink-2)", lineHeight: "var(--lh-body)" } }, s.intro)),
      el("ol", { class: "g-2", style: { margin: 0, padding: 0, listStyle: "none" } },
        s.items.map(function (it) {
          return el("li", { style: { display: "grid", gridTemplateColumns: "26px minmax(0,1fr)", columnGap: "var(--sp-4)", borderTop: "1px solid var(--line-strong)", paddingTop: "var(--sp-5)", alignContent: "start" } },
            el("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--t-ui)", color: "var(--ink-3)", fontVariantNumeric: "tabular-nums", lineHeight: "var(--lh-ui)" } }, it.n),
            el("h3", { style: { fontSize: "var(--t-h4)", letterSpacing: "-0.01em", margin: 0, lineHeight: "var(--lh-ui)" } }, it.title),
            el("p", { style: { gridColumn: 2, margin: "var(--sp-4) 0 0", fontSize: "var(--t-small)", color: "var(--ink-2)", lineHeight: "var(--lh-body)" } }, S.rich(it.body)));
        }))));
  }

  /* ── S7 · the team ──
     Contribution statements, not credit lines. The hand survey is what makes S5
     mean anything, so the field-measurement entry carries the same weight as
     the other two. No portraits and no social links: the copy provides none. */
  function team(c) {
    var s = c.s7;
    return el("section", { id: "s7" }, el("div", { class: "wrap" },
      el("h2", { style: { fontSize: "var(--t-h1)", letterSpacing: "-0.024em", lineHeight: 1.1, margin: "0 0 var(--sp-10)" } }, s.h2),
      el("div", { style: { display: "grid", gap: "var(--sp-10)" } },
        s.people.map(function (p) {
          return el("article", { class: "g-person", style: { borderTop: "1px solid var(--line-strong)", paddingTop: "var(--sp-6)" } },
            el("header", {},
              el("h3", { style: { fontSize: "var(--t-h3)", letterSpacing: "-0.014em", margin: "0 0 var(--sp-3)" } }, p.name),
              el("p", { style: { margin: 0, fontSize: "var(--t-small)", color: "var(--ink-3)", lineHeight: "var(--lh-ui)" } }, p.role)),
            el("div", {}, p.paras.map(function (t, i) {
              return el("p", { style: { margin: i ? "var(--sp-5) 0 0" : 0, fontSize: "var(--t-body)", color: "var(--ink-2)", lineHeight: "var(--lh-body)", maxWidth: "var(--measure)" } }, t);
            })));
        }))));
  }

  /* ── S8 · footer ── the live app first: a juror clicks the working thing */
  function footer(c) {
    var s = c.s8;
    return el("footer", { id: "s8", class: "site-foot" }, el("div", { class: "wrap", style: { paddingTop: "var(--sp-10)", paddingBottom: "var(--sp-10)" } },
      el("div", { class: "g-foot" },
        el("div", {},
          el("img", { src: "assets/logo-lockup-on-charcoal.svg", alt: "Smart Road", style: { height: 22, display: "block", marginBottom: "var(--sp-6)" } }),
          el("p", { style: { margin: 0, fontFamily: "var(--font-mono)", fontSize: "var(--t-caption)", color: "rgba(237,237,234,.62)", letterSpacing: "0.02em" } }, s.licence)),
        el("div", {},
          el("ul", { class: "g-foot-links" }, s.links.map(function (l) {
            return el("li", {}, el("a", { href: l.href, target: "_blank", rel: "noopener" }, l.label));
          })),
          el("p", { style: { margin: "var(--sp-8) 0 0", fontSize: "var(--t-caption)", lineHeight: "var(--lh-caption)", color: "rgba(237,237,234,.62)", maxWidth: "var(--measure-note)" } }, s.note)))));
  }

  /* ── boot ──
     All three languages ship in the page (copy.js); switching re-renders from
     that object and never fetches. The choice is reflected in ?lang= so a juror
     can be sent straight to one language and a reload keeps it, and <html lang>
     follows so screen readers and the browser treat the text correctly. */
  var LANGS = ["uz", "ru", "en"];
  var state = { lang: "uz", theme: "dark" };

  function readUrl() {
    var q = new URLSearchParams(location.search).get("lang");
    if (q && LANGS.indexOf(q) > -1) state.lang = q;
    var t = new URLSearchParams(location.search).get("theme");
    if (t === "light" || t === "dark") state.theme = t;
  }

  function writeUrl() {
    var u = new URL(location.href);
    if (state.lang === "uz") u.searchParams.delete("lang"); else u.searchParams.set("lang", state.lang);
    history.replaceState(null, "", u.toString().replace(/\?$/, ""));
  }

  function set(patch) {
    var hash = location.hash;
    Object.assign(state, patch);
    writeUrl();
    render();
    if (hash) { var t = document.getElementById(hash.slice(1)); if (t) t.scrollIntoView({ block: "start" }); }
  }

  function render() {
    var c = w.SR_COPY[state.lang];
    c.__lang = state.lang;
    document.documentElement.setAttribute("data-theme", state.theme);
    document.documentElement.lang = state.lang;
    var root = document.getElementById("root");
    root.innerHTML = "";
    [header(c, state, set), hero(c), argument(c), pipeline(c), demo(c), validation(c), limits(c), team(c), footer(c)]
      .forEach(function (n) { root.appendChild(n); });
    if (w.fitUzbek) w.fitUzbek(root);
  }

  readUrl();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render);
  else render();
})(window);
