"""Regenerate `smartroad/pci/curves.py` from the upstream Ruby gem.

ASTM D6433 publishes its deduct-value curves as printed graphs, not equations,
so every implementation has to digitise them. Rather than re-read the charts by
eye, this takes the polynomial fits from the MIT-licensed
`brandnewbox/pavement_condition_index` gem, which did that work.

The gem stores them as Ruby hash literals. Ruby's `:symbol => value` syntax is
close enough to Python's dict literal that a handful of regex substitutions plus
`ast.literal_eval` converts them safely -- `literal_eval` refuses to execute
code, so a malformed or hostile source fails loudly instead of running.

Run from the repository root:

    .venv/bin/python tools/gen_curves.py

Sources are read from a local clone under DATA/reference if one exists, and
fetched from GitHub otherwise. Both paths produce identical output; the local
clone just avoids the network.
"""
from __future__ import annotations

import argparse
import ast
import pprint
import re
import sys
import urllib.request
from pathlib import Path

REPO = "brandnewbox/pavement_condition_index"
RAW = f"https://raw.githubusercontent.com/{REPO}/master"
LOOKUPS = "lib/pavement_condition_index/lookups"

LOCAL_CLONE = Path("DATA/reference/pavement_condition_index_ruby")
OUT = Path("smartroad/pci/curves.py")

SOURCES = {
    "deduct": "calculated_deduct_coefficients.rb",
    "cdv": "calculated_corrected_deduct_coefficients.rb",
}

HEADER = '''"""ASTM D6433 deduct-value and corrected-deduct-value curve coefficients.

AUTO-GENERATED -- do not edit by hand.

ASTM publishes these curves as printed graphs, not equations, so every software
implementation has to digitise them. These coefficients come from the MIT-licensed
`brandnewbox/pavement_condition_index` Ruby gem, which read points off the D6433
charts and fitted a polynomial per curve. Regenerate with tools/gen_curves.py.

A deduct value is evaluated as a polynomial in log10(density) for asphalt
(`chart_type == "log"`) or in the raw density for concrete:

    DV = sum(c[i] * x**i)   where x = log10(density_pct) or density_pct

`valid_min` / `valid_max` are the density bounds of the printed chart; densities
outside are clamped, because extrapolating a fitted polynomial past the data it
was fitted to produces nonsense.

Corrected deduct values use one polynomial per q (number of deducts above 2.0),
evaluated on the total deduct value.
"""
'''


def read_source(filename: str) -> str:
    local = LOCAL_CLONE / LOOKUPS / filename
    if local.is_file():
        return local.read_text()
    url = f"{RAW}/{LOOKUPS}/{filename}"
    print(f"  yuklanmoqda {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=60) as fh:
        return fh.read().decode("utf-8")


def ruby_hash_to_python(src: str) -> dict:
    """Convert the `COEFFICIENTS = {...}` literal in a lookup file to a dict."""
    i = src.index("COEFFICIENTS")
    src = src[src.index("{", i):]
    # Trim everything after the literal's matching brace, so the module's
    # trailing `end`s do not reach literal_eval.
    depth = 0
    for j, ch in enumerate(src):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                src = src[: j + 1]
                break
    else:
        raise ValueError("unbalanced braces in COEFFICIENTS literal")

    src = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)\s*=>", r'"\1":', src)  # :key=> -> "key":
    src = re.sub(r"=>", ":", src)
    src = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)\b", r'"\1"', src)      # bare :symbol values
    return ast.literal_eval(src)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    tables = {k: ruby_hash_to_python(read_source(v)) for k, v in SOURCES.items()}
    deduct, cdv = tables["deduct"], tables["cdv"]

    # Guard rails: a silently truncated parse would still write a valid module,
    # and a missing distress only shows up much later as a PCI that is too high.
    if set(deduct) != {"asphalt", "concrete"}:
        raise SystemExit(f"kutilmagan qoplama turlari: {sorted(deduct)}")
    if len(deduct["asphalt"]) < 19:
        raise SystemExit(f"asfalt nuqsonlari juda kam: {len(deduct['asphalt'])}")
    if len(cdv["asphalt"]["coefficients"]) < 7:
        raise SystemExit("CDV q-egri chiziqlari yetishmaydi")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        f.write(HEADER)
        f.write("\nDEDUCT_CURVES = ")
        f.write(pprint.pformat(deduct, width=100, sort_dicts=True))
        f.write("\n\nCDV_CURVES = ")
        f.write(pprint.pformat(cdv, width=100, sort_dicts=True))
        f.write("\n")

    print(f"yozildi {args.out}  {args.out.stat().st_size} bayt")
    print(f"  asfalt nuqsonlari : {len(deduct['asphalt'])}")
    print(f"  beton nuqsonlari  : {len(deduct['concrete'])}")
    print(f"  CDV q-egrilari    : {sorted(cdv['asphalt']['coefficients'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
