/* Fit the Uzbek modifier apostrophes U+02BB / U+02BC.

   IBM Plex Sans draws U+02BB with the sidebearings of an English quotation
   mark — measured at 100 px, 11.8 units of ink inside a 60.0 unit advance, 80 %
   air. Uzbek sets it INSIDE a word, so oʻ and gʻ read as broken words:
   "o ʻ lchandi". The codepoint is never changed here, only the fit, by the
   .sr-oz rule in styles.css. Text copied out of the page stays orthographically
   correct Uzbek.

   Each affected text node becomes ONE <span class="sr-oz-run">: a text node
   inside a flex container is a single anonymous flex item, and splitting it
   into three would let the container's `gap` open up on both sides of the
   apostrophe — the exact defect this file exists to prevent.

   Idempotent; skips script/style/textarea/code/pre. Called after every render.

   Delete this file the day the Plex subsets carry corrected advance widths for
   the two glyphs — then neither this pass nor the .sr-oz rule is needed. */
(function (global) {
  var RE = /[\u02BB\u02BC]/;
  var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, CODE: 1, PRE: 1 };

  function fitUzbek(root) {
    root = root || document.body;
    if (!root) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var p = n.parentNode;
        if (!p || SKIP[p.nodeName]) return NodeFilter.FILTER_REJECT;
        if (p.classList && (p.classList.contains("sr-oz") || p.classList.contains("sr-oz-run"))) return NodeFilter.FILTER_REJECT;
        return RE.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    var nodes = [], n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function (node) {
      var run = document.createElement("span");
      run.className = "sr-oz-run";
      node.nodeValue.split(/([\u02BB\u02BC])/).forEach(function (part) {
        if (!part) return;
        if (part.length === 1 && RE.test(part)) {
          var s = document.createElement("span");
          s.className = "sr-oz";
          s.textContent = part;
          run.appendChild(s);
        } else {
          run.appendChild(document.createTextNode(part));
        }
      });
      node.parentNode.replaceChild(run, node);
    });
  }

  global.fitUzbek = fitUzbek;
})(window);
