/* Smart Road — static site, part 1: helpers and the components the sections
   compose. No framework: everything here builds DOM nodes directly.

   These are hand ports of the design system's React components. If one of them
   changes upstream, change it here too — the file each came from is named in
   the comment above it. */
(function (w) {
  "use strict";

  /* ── element helper ──
     el("div", {style:{...}, class:"x", onclick:fn, ...attrs}, ...children)
     A style object is written as inline CSS so a component's look sits next to
     the markup that produces it; anything needing a media query or a
     pseudo-class lives in site.css instead. */
  /* CSS properties whose values are unitless numbers. Everything else gets px
     when handed a number — so `gridColumn: 2` must be listed here, or it becomes
     `grid-column: 2px`, silently invalid, and the element lands in the wrong
     track. */
  var UNITLESS = { flex: 1, flexGrow: 1, flexShrink: 1, opacity: 1, zIndex: 1, lineHeight: 1, order: 1,
    fontWeight: 1, gridColumn: 1, gridRow: 1, gridColumnStart: 1, gridColumnEnd: 1, gridRowStart: 1,
    gridRowEnd: 1, columnCount: 1, zoom: 1, tabSize: 1 };

  function css(o) {
    var s = "";
    for (var k in o) {
      if (o[k] == null || o[k] === false) continue;
      var prop = k.replace(/[A-Z]/g, function (m) { return "-" + m.toLowerCase(); });
      var v = o[k];
      if (typeof v === "number" && v !== 0 && !UNITLESS[k]) v += "px";
      s += prop + ":" + v + ";";
    }
    return s;
  }

  function el(tag, props) {
    var n = document.createElement(tag), i;
    props = props || {};
    for (var k in props) {
      var v = props[k];
      if (v == null || v === false) continue;
      if (k === "style") n.style.cssText = typeof v === "string" ? v : css(v);
      else if (k === "class") n.className = v;
      else if (k === "html") n.innerHTML = v;
      else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (i = 2; i < arguments.length; i++) add(n, arguments[i]);
    return n;
  }

  function add(parent, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) { c.forEach(function (x) { add(parent, x); }); return; }
    parent.appendChild(c.nodeType ? c : document.createTextNode(String(c)));
  }

  var NS = "http://www.w3.org/2000/svg";
  function svg(tag, props) {
    var n = document.createElementNS(NS, tag);
    props = props || {};
    for (var k in props) {
      if (props[k] == null || props[k] === false) continue;
      if (k === "style") n.setAttribute("style", typeof props[k] === "string" ? props[k] : css(props[k]));
      else n.setAttribute(k, props[k]);
    }
    for (var i = 2; i < arguments.length; i++) add(n, arguments[i]);
    return n;
  }

  /* ── copy helpers ── */
  var LABEL = { fontFamily: "var(--font-sans)", fontSize: "var(--t-micro)", fontWeight: "var(--fw-semibold)", letterSpacing: "var(--track-label)", textTransform: "uppercase", color: "var(--ink-3)" };
  var MONO = { fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" };

  /* A copy string may be an array: a plain string is text, {v} a measured value
     (mono), {b} an emphasis (semibold sans). Keeps the mono/sans split honest
     inside a sentence without any component rewriting the words. */
  function rich(parts) {
    var f = document.createDocumentFragment();
    (Array.isArray(parts) ? parts : [parts]).forEach(function (p) {
      if (typeof p === "string") { f.appendChild(document.createTextNode(p)); return; }
      if (p.v != null) f.appendChild(el("span", { style: { fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--ink-1)" } }, p.v));
      else f.appendChild(el("strong", { style: { fontWeight: "var(--fw-semibold)", color: "var(--ink-1)" } }, p.b));
    });
    return f;
  }

  function label(text, extra) {
    var s = {}; for (var k in LABEL) s[k] = LABEL[k];
    for (var j in (extra || {})) s[j] = extra[j];
    return el("div", { style: s }, text);
  }

  /* Figure marker. "Fig." is a word (sans); the number is a value (mono). */
  function figMark(n) {
    return el("span", { style: { flex: "0 0 auto", fontFamily: "var(--font-sans)", fontSize: "var(--t-micro)", fontWeight: "var(--fw-semibold)", letterSpacing: "var(--track-label)", textTransform: "uppercase", color: "var(--accent-ink)", paddingTop: 2 } },
      "Fig.\u00a0", el("span", { style: { fontFamily: "var(--font-mono)", letterSpacing: 0 } }, String(n)));
  }

  function caption(n, text, source) {
    return el("figcaption", { style: { display: "flex", gap: "var(--sp-4)", marginTop: "var(--sp-4)", maxWidth: "var(--measure-note)", fontSize: "var(--t-caption)", lineHeight: "var(--lh-caption)", color: "var(--ink-2)" } },
      n != null ? figMark(n) : null,
      el("span", {}, text, source ? el("span", { style: { fontFamily: "var(--font-mono)", color: "var(--ink-3)" } }, " " + source) : null));
  }

  /* ── core/Button.jsx ── chrome only; brand orange never carries a measurement */
  function button(text, size, onclick) {
    return el("button", { type: "button", class: "btn btn-primary btn-" + (size || "sm"), onclick: onclick }, text);
  }

  /* ── core/LanguageSwitcher.jsx ──
     Permanent chrome. All three states always visible, always in this order,
     codes always Latin so the control never changes width between locales. */
  var LANGS = [{ code: "uz", short: "UZ", name: "Oʻzbekcha" }, { code: "ru", short: "RU", name: "Русский" }, { code: "en", short: "EN", name: "English" }];
  function langSwitcher(value, onChange) {
    return el("div", { class: "lang", role: "group", "aria-label": "Til / Язык / Language" },
      LANGS.map(function (l) {
        return el("button", { type: "button", lang: l.code, title: l.name, "aria-pressed": l.code === value ? "true" : "false", onclick: function () { onChange(l.code); } }, l.short);
      }));
  }

  /* ── core/SegmentedControl.jsx ── */
  function segmented(options, value, onChange, ariaLabel) {
    return el("div", { class: "seg", role: "radiogroup", "aria-label": ariaLabel },
      options.map(function (o) {
        return el("button", { type: "button", role: "radio", "aria-checked": o.value === value ? "true" : "false", onclick: function () { onChange(o.value); } }, o.label);
      }));
  }

  /* ── data/MetricTile.jsx ── label is a word, value is a measurement */
  function metricTile(t) {
    return el("div", { style: { background: "var(--surface-1)", border: "1px solid var(--line-1)", borderRadius: "var(--r-4)", padding: "14px 16px", boxShadow: "var(--shadow-1)" } },
      label(t.label),
      el("div", { style: { display: "flex", alignItems: "baseline", gap: 5, margin: "6px 0 2px", fontFamily: "var(--font-mono)", fontSize: "var(--t-h2)", fontWeight: "var(--fw-semibold)", letterSpacing: "-0.025em", lineHeight: 1.05, color: "var(--ink-1)", fontVariantNumeric: "tabular-nums" } },
        t.value,
        t.unit ? el("span", { style: { fontSize: "var(--t-ui)", fontWeight: "var(--fw-regular)", color: "var(--ink-3)", letterSpacing: 0 } }, t.unit) : null),
      t.sub ? el("div", { style: { fontSize: "var(--t-caption)", color: "var(--ink-3)", lineHeight: "var(--lh-caption)" } }, t.sub) : null);
  }

  /* ── data/Callout.jsx ── a stated limit, never an afterthought */
  var TONES = { note: "var(--line-strong)", limit: "var(--data-1)", warning: "var(--band-poor)" };
  function callout(tone, labelText, body) {
    return el("aside", { style: { borderLeft: "2px solid " + (TONES[tone] || TONES.note), padding: "2px 0 2px var(--sp-5)", maxWidth: "var(--measure)" } },
      labelText ? label(labelText, { color: tone === "warning" ? "var(--band-poor)" : "var(--ink-3)", marginBottom: 4 }) : null,
      el("div", { style: { fontSize: "var(--t-small)", color: "var(--ink-2)", lineHeight: "var(--lh-body)" } }, body));
  }

  /* ── analysis/DetectionOverlay.jsx ──
     Photograph, the surface actually searched, and labelled boxes. Geometry is
     in percentages so the overlay survives any render size. A box flagged
     `seam` touches a tile boundary and is drawn dashed: the pipeline refuses to
     merge those silently, and neither does the drawing.

     Labels are collision-tested against the measured render width and the loser
     is dropped rather than printed on top of its neighbour; the box, its colour
     and its title attribute stay, so no detection is lost silently. */
  function classVar(c) { return "var(--class-" + c.replace(/_/g, "-") + ")"; }

  function detectionOverlay(src, roi, boxes, radius) {
    var wrapper = el("div", { style: { position: "relative", width: "100%", background: "var(--surface-inset)", borderRadius: radius == null ? "var(--r-4)" : radius, overflow: "hidden", lineHeight: 0 } },
      el("img", { src: src, alt: "", loading: "lazy", style: { width: "100%", display: "block" } }),
      roi ? el("div", { "aria-hidden": "true", style: { position: "absolute", left: (roi.x || 0) + "%", top: roi.y + "%", width: (roi.w || 100) + "%", height: roi.h + "%", border: "1px solid var(--roi-outline)", background: "var(--roi-fill)", pointerEvents: "none" } }) : null);

    var labels = [];
    boxes.forEach(function (d) {
      var box = el("div", { title: d.label || "", style: { position: "absolute", left: d.x + "%", top: d.y + "%", width: d.w + "%", height: d.h + "%", border: "var(--box-stroke-width) " + (d.seam ? "dashed" : "solid") + " " + classVar(d.cls), borderRadius: 1 } });
      if (d.label) {
        var lab = el("span", { style: { position: "absolute", left: -2, top: -17, whiteSpace: "nowrap", padding: "1px 4px", background: "var(--box-label-scrim)", color: classVar(d.cls), fontFamily: "var(--font-mono)", fontSize: "var(--t-micro)", lineHeight: 1.35, letterSpacing: "0.02em", borderRadius: 2 } }, d.label);
        box.appendChild(lab);
        labels.push({ d: d, node: lab });
      }
      wrapper.appendChild(box);
    });

    function place() {
      var W = wrapper.clientWidth;
      if (!W) return;
      var taken = [];
      labels.forEach(function (L) {
        L.node.style.display = "";
        var left = (L.d.x / 100) * W - 2;
        var right = left + L.node.offsetWidth;
        var top = (L.d.y / 100) * W * 0.5625;
        var clash = taken.some(function (p) { return Math.abs(p.top - top) < 18 && left < p.right + 4 && right + 4 > p.left; });
        if (clash) L.node.style.display = "none";
        else taken.push({ left: left, right: right, top: top });
      });
    }
    if (labels.length > 1 && typeof ResizeObserver !== "undefined") new ResizeObserver(place).observe(wrapper);
    requestAnimationFrame(place);
    return wrapper;
  }

  /* ── analysis/DetectionLegend.jsx ── */
  function detectionLegend(lang, only, columns) {
    var items = window.SR_CLASSES.filter(function (c) { return !only || only.indexOf(c.cls) > -1; });
    return el("ul", { style: { listStyle: "none", margin: 0, padding: 0, display: "grid", gridTemplateColumns: "repeat(" + (columns || 2) + ",minmax(0,1fr))", gap: "var(--sp-2) var(--sp-6)" } },
      items.map(function (c) {
        return el("li", { style: { display: "flex", alignItems: "baseline", gap: "var(--sp-3)", fontSize: "var(--t-caption)", lineHeight: "var(--lh-ui)", color: c.astm != null ? "var(--ink-2)" : "var(--ink-3)" } },
          el("span", { style: { flex: "0 0 auto", width: 10, height: 10, borderRadius: 2, marginTop: 3, background: classVar(c.cls) } }),
          el("span", { style: { minWidth: 0 } }, c[lang],
            el("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--t-micro)", color: "var(--ink-3)", whiteSpace: "nowrap" } }, c.astm != null ? "  ASTM " + c.astm : "  —")));
      }));
  }

  /* ── condition/ConditionScale.jsx ── the standard's scale as a ruler */
  function conditionScale(pci, lang) {
    var ramp = window.SR_BANDS.slice().reverse();
    var ends = { uz: ["Yaroqsiz", "Oʻrtacha", "Yaxshi"], ru: ["Непригодное", "Посредственное", "Хорошее"], en: ["Failed", "Fair", "Good"] }[lang];
    var p = Math.max(0, Math.min(100, pci));
    return el("div", {},
      el("div", { style: { display: "flex", height: 8, borderRadius: 1, overflow: "hidden" } },
        ramp.map(function (b, i) {
          var hi = i + 1 < ramp.length ? ramp[i + 1].min : 100;
          return el("div", { style: { flex: hi - b.min, background: "var(--band-" + b.key + ")" } });
        })),
      el("div", { style: { position: "relative", height: 8 } },
        el("span", { style: { position: "absolute", left: p + "%", transform: "translateX(-50%)", width: 0, height: 0, borderLeft: "4px solid transparent", borderRight: "4px solid transparent", borderBottom: "5px solid var(--ink-1)", marginTop: 2 } })),
      el("div", { style: { display: "flex", justifyContent: "space-between", fontSize: "var(--t-micro)", color: "var(--ink-3)" } },
        [0, 55, 100].map(function (n, i) {
          return el("span", {}, el("span", { style: MONO }, String(n)), " " + ends[i]);
        })));
  }

  /* ── condition/ScoreCard.jsx ──
     Condition colour MARKS, it does not flood: the band is carried by a rule
     under the numeral, a swatch beside the band name and the marker on the
     scale. A filled panel would turn a measurement into an alarm. */
  var BAND_NAMES = {
    good: { uz: "Yaxshi", ru: "Хорошее", en: "Good" },
    satisfactory: { uz: "Qoniqarli", ru: "Удовлетворительное", en: "Satisfactory" },
    fair: { uz: "Oʻrtacha", ru: "Посредственное", en: "Fair" },
    poor: { uz: "Yomon", ru: "Плохое", en: "Poor" },
    "very-poor": { uz: "Juda yomon", ru: "Очень плохое", en: "Very Poor" },
    serious: { uz: "Ogʻir", ru: "Тяжёлое", en: "Serious" },
    failed: { uz: "Yaroqsiz", ru: "Непригодное", en: "Failed" },
  };
  var SCORE_LABEL = { uz: "Yoʻl qoplamasi indeksi", ru: "Индекс состояния покрытия", en: "Pavement condition index" };

  function scoreCard(pci, lang, decimals) {
    var key = window.srBand(pci);
    return el("div", {},
      label(SCORE_LABEL[lang]),
      el("div", { style: { display: "flex", alignItems: "baseline", gap: "var(--sp-5)", flexWrap: "wrap", margin: "var(--sp-3) 0 0" } },
        el("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--t-score)", fontWeight: "var(--fw-semibold)", lineHeight: 0.94, letterSpacing: "-0.03em", fontVariantNumeric: "tabular-nums", color: "var(--ink-1)" } }, w.srNum(pci, lang, decimals == null ? 1 : decimals)),
        el("span", { style: { display: "flex", alignItems: "center", gap: "var(--sp-3)", whiteSpace: "nowrap" } },
          el("span", { style: { width: 10, height: 10, borderRadius: 2, background: "var(--band-" + key + ")", flex: "0 0 auto" } }),
          el("span", { style: { fontSize: "var(--t-h4)", fontWeight: "var(--fw-semibold)", color: "var(--ink-1)", letterSpacing: "var(--track-heading)" } }, BAND_NAMES[key][lang]))),
      el("div", { style: { height: 3, background: "var(--band-" + key + ")", marginTop: "var(--sp-4)" } }),
      el("div", { style: { marginTop: "var(--sp-5)" } }, conditionScale(pci, lang)));
  }

  /* ── analysis/DeductChain.jsx ──
     Densities → deduct values → corrected deduct value → PCI. The step chart
     shares one scale across all three rows, so the correction reads as a
     reduction and the PCI as what is left of 100. */
  var CHAIN_T = {
    uz: { d: "Nuqson", n: "n", q: "Miqdor", dens: "Zichlik", dv: "Deduct", tdv: "Deduct qiymatlari", cdv: "Tuzatilgan (q = ", pci: "PCI = 100 −" },
    ru: { d: "Дефект", n: "n", q: "Количество", dens: "Плотность", dv: "Вычет", tdv: "Значения вычета", cdv: "Скорректировано (q = ", pci: "PCI = 100 −" },
    en: { d: "Distress", n: "n", q: "Quantity", dens: "Density", dv: "Deduct", tdv: "Deduct values", cdv: "Corrected (q = ", pci: "PCI = 100 −" },
  };

  function chainRow(labelText, value, bar, strong) {
    return el("div", { style: { display: "grid", gridTemplateColumns: "minmax(120px,170px) 1fr 56px", alignItems: "center", gap: "var(--sp-4)" } },
      el("span", { style: { fontFamily: "var(--font-sans)", fontSize: "var(--t-caption)", color: "var(--ink-2)" } }, labelText),
      el("div", { style: { background: "var(--track)", height: 12 } }, bar),
      el("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--t-small)", textAlign: "right", color: strong ? "var(--ink-1)" : "var(--ink-2)", fontWeight: strong ? "var(--fw-semibold)" : "var(--fw-regular)", fontVariantNumeric: "tabular-nums" } }, value));
  }

  function deductChain(cfg, lang) {
    var t = CHAIN_T[lang];
    var dec = function (s) { return lang === "ru" ? String(s).replace(".", ",") : String(s); };
    var name = function (d) { return d && typeof d === "object" ? (d[lang] || d.en) : d; };
    /* Units are language too: Russian writes м², not m². */
    var unit = name;
    var rows = cfg.rows;
    var tdv = rows.reduce(function (s, r) { return s + r.deduct; }, 0);
    var scale = Math.max(100, tdv);
    var wpc = function (v) { return (v / scale) * 100 + "%"; };
    var cell = { padding: "7px 10px", borderBottom: "1px solid var(--line-1)", fontSize: "var(--t-small)" };
    var num = { padding: cell.padding, borderBottom: cell.borderBottom, fontSize: cell.fontSize, textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" };

    return el("div", {},
      el("table", { style: { width: "100%", borderCollapse: "collapse" } },
        el("thead", {}, el("tr", {}, [t.d, t.n, t.q, t.dens, t.dv].map(function (h, i) {
          return el("th", { style: { padding: "6px 10px", textAlign: i === 0 ? "left" : "right", background: "var(--surface-2)", color: "var(--ink-2)", fontSize: "var(--t-caption)", fontWeight: "var(--fw-semibold)", borderBottom: "1px solid var(--line-2)", whiteSpace: "nowrap" } }, h);
        }))),
        el("tbody", {}, rows.map(function (r) {
          return el("tr", {},
            el("td", { style: cell }, name(r.distress)),
            el("td", { style: num }, String(r.n)),
            el("td", { style: num }, dec(r.quantity), el("span", { style: { color: "var(--ink-3)" } }, " " + unit(r.unit))),
            el("td", { style: num }, dec(r.density), el("span", { style: { color: "var(--ink-3)" } }, " %")),
            el("td", { style: Object.assign({}, num, { color: "var(--ink-1)", fontWeight: "var(--fw-medium)" }) }, dec(r.deduct.toFixed(1))));
        }))),
      el("div", { style: { marginTop: "var(--sp-6)", display: "grid", gap: "var(--sp-3)" } },
        chainRow(t.tdv, dec(tdv.toFixed(1)),
          el("div", { style: { display: "flex", width: wpc(tdv), height: 12, gap: 1 } },
            rows.map(function (r, i) {
              return el("div", { title: name(r.distress) + " " + r.deduct.toFixed(1), style: { flex: r.deduct, background: i === 0 ? "var(--data-1)" : i === 1 ? "var(--data-2)" : "var(--data-3)" } });
            }))),
        chainRow(t.cdv + cfg.q + ")", dec(cfg.maxCdv.toFixed(1)),
          el("div", { style: { width: wpc(cfg.maxCdv), height: 12, background: "var(--data-1)" } })),
        chainRow(t.pci + " " + dec(cfg.maxCdv.toFixed(1)), dec(cfg.pci.toFixed(1)),
          el("div", { style: { width: wpc(cfg.pci), height: 12, background: "var(--band-" + w.srBand(cfg.pci) + ")" } }), true),
        el("div", { style: { display: "flex", justifyContent: "space-between", fontFamily: "var(--font-mono)", fontSize: "var(--t-micro)", color: "var(--ink-3)", paddingLeft: 186, paddingRight: 68 } },
          el("span", {}, "0"), el("span", {}, String(scale > 100 ? Math.round(scale / 2) : 50)), el("span", {}, String(Math.round(scale))))));
  }

  /* ── data/VideoBlock.jsx ──
     A recording offered as evidence: poster, one control, a mono meta line.
     No autoplay and no player chrome — a reader is being invited to check a
     claim, not served a media feature. */
  function videoBlock(poster, src, labelText, meta) {
    var frame = el("div", { style: { position: "relative", background: "var(--surface-inset)", border: "1px solid var(--line-1)", borderRadius: "var(--r-4)", overflow: "hidden", lineHeight: 0 } },
      el("img", { src: poster, alt: "", loading: "lazy", style: { width: "100%", display: "block" } }));
    var play = el("button", { type: "button", class: "play", "aria-label": labelText, onclick: function () {
      if (!src) return;
      frame.innerHTML = "";
      frame.appendChild(el("video", { src: src, poster: poster, controls: true, autoplay: true, style: { width: "100%", display: "block" } }));
    } }, el("span", { class: "play-dot" }, el("span", { class: "play-tri" })), labelText);
    frame.appendChild(play);
    return el("figure", { style: { margin: 0 } }, frame,
      meta ? el("figcaption", { style: { marginTop: "var(--sp-4)", fontFamily: "var(--font-mono)", fontSize: "var(--t-caption)", color: "var(--ink-3)" } }, meta) : null);
  }

  w.SR = { el: el, svg: svg, css: css, rich: rich, label: label, caption: caption, figMark: figMark, button: button,
    langSwitcher: langSwitcher, segmented: segmented, metricTile: metricTile, callout: callout,
    detectionOverlay: detectionOverlay, detectionLegend: detectionLegend, conditionScale: conditionScale,
    scoreCard: scoreCard, deductChain: deductChain, videoBlock: videoBlock, MONO: MONO, LABEL: LABEL };
})(window);
