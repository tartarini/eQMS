"""Write README badges (SVG, shields.io "flat" style) from CI results.

    python .github/scripts/badges.py coverage.json oq_evidence/oq_results.json badges/

Writes coverage.svg, tests.svg and oq.svg. No network access or third-party service: CI
publishes the files to the `badges` branch, and the README links to them there.
"""
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

# Approximate Verdana 11px advance widths, as shields.io uses; good enough for short labels.
NARROW, WIDE = set("fijlrtI1.,:;!|' ()"), set("mwMW%@")  # the rest are about 7px


def text_width(text: str) -> int:
    return int(sum(4.0 if c in NARROW else 10.0 if c in WIDE else 8.5 if c.isupper() else 7.0
                   for c in text)) + 10


def fit(width: int) -> str:
    """Stretch or squeeze the text to its box, so it fits whatever font the viewer has."""
    return f'textLength="{width - 10}" lengthAdjust="spacingAndGlyphs"'


def badge(label: str, message: str, color: str) -> str:
    lw, mw = text_width(label), text_width(message)
    w = lw + mw
    label, message = escape(label), escape(message)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{label}: {message}">
<title>{label}: {message}</title>
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
<clipPath id="r"><rect width="{w}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#555"/><rect x="{lw}" width="{mw}" height="20" fill="{color}"/><rect width="{w}" height="20" fill="url(#s)"/></g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
<text x="{lw / 2}" y="15" fill="#010101" fill-opacity=".3" {fit(lw)}>{label}</text><text x="{lw / 2}" y="14" {fit(lw)}>{label}</text>
<text x="{lw + mw / 2}" y="15" fill="#010101" fill-opacity=".3" {fit(mw)}>{message}</text><text x="{lw + mw / 2}" y="14" {fit(mw)}>{message}</text>
</g></svg>
"""


def coverage_color(pct: float) -> str:
    for limit, color in ((90, "#4c1"), (80, "#97ca00"), (70, "#a4a61d"), (60, "#dfb317")):
        if pct >= limit:
            return color
    return "#e05d44"


def main(coverage_json: str, oq_json: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pct = json.loads(Path(coverage_json).read_text())["totals"]["percent_covered"]
    (out / "coverage.svg").write_text(badge("coverage", f"{pct:.0f}%", coverage_color(pct)))

    summary = json.loads(Path(oq_json).read_text())["summary"]
    failed = len(summary["tests_failed"])
    tests = (f"{summary['tests_passed']} passed", "#4c1") if not failed else \
        (f"{failed} failed, {summary['tests_passed']} passed", "#e05d44")
    (out / "tests.svg").write_text(badge("tests", *tests))
    ok = summary["overall"] == "PASS"
    oq = f"{summary['requirements']} requirements traced" if ok else "failed"
    (out / "oq.svg").write_text(badge("OQ", oq, "#4c1" if ok else "#e05d44"))
    print(f"coverage {pct:.1f}%, tests {tests[0]}, OQ {oq}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
