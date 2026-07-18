#!/usr/bin/env python3
"""
Daily market-mover news digest.

Runs on the GitHub Actions runner (has internet). Pulls last-24h headlines
via free Google News RSS for:
  - people whose posts move markets (Trump, Musk, Fed chair, Treasury)
  - macro catalysts (oil / Iran / OPEC, rates, tariffs)
  - our watchlist themes (chips, energy, banks)
  - general "stock market today"

Writes news.md (human digest) + news.json (machine-readable). A MOVERS
section highlights headlines mentioning key market-moving figures so the
signal analysis can react to them.

Note: direct Twitter/X access needs the paid API, so we don't read tweets
firsthand. Financial media report market-moving tweets within minutes, so
these keyword searches capture the market impact just as well.
"""

import datetime as dt
import html
import json
import re
import sys
from pathlib import Path
from urllib import parse as urlparse
from urllib import request as urlrequest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
NEWS_JSON = ROOT / "news.json"
NEWS_MD = ROOT / "news.md"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)

# (label, query). when:1d limits to the last day.
QUERIES = [
    ("Market",   "US stock market today when:1d"),
    ("Trump",    "Trump stock market OR tariffs OR Iran when:1d"),
    ("Musk",     "Elon Musk Tesla when:1d"),
    ("Fed",      "Federal Reserve interest rates Powell when:1d"),
    ("Oil",      "oil price Iran OPEC Hormuz when:1d"),
    ("Chips",    "Nvidia AMD semiconductor stocks when:1d"),
    ("Earnings", "earnings today stock movers when:1d"),
]

# Headlines mentioning any of these get flagged as market MOVERS.
MOVER_KEYWORDS = [
    "trump", "musk", "powell", "fed", "federal reserve", "tariff",
    "iran", "opec", "hormuz", "war", "strike", "sanction", "rate cut",
    "rate hike", "cpi", "inflation", "recession", "jobs report",
]

PER_QUERY = 5


def fetch_rss(query: str) -> list:
    url = ("https://news.google.com/rss/search?q="
           + urlparse.quote(query)
           + "&hl=en-US&gl=US&ceid=US:en")
    req = urlrequest.Request(url, headers={"User-Agent": BROWSER_UA})
    with urlrequest.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    items = []
    for it in root.iter("item"):
        title = it.findtext("title") or ""
        link = it.findtext("link") or ""
        pub = it.findtext("pubDate") or ""
        source_el = it.find("source")
        source = source_el.text if source_el is not None else ""
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        items.append({"title": title, "link": link, "pub": pub, "source": source})
        if len(items) >= PER_QUERY:
            break
    return items


def is_mover(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in MOVER_KEYWORDS)


def main() -> int:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    sections = {}
    movers = []
    errors = {}
    seen = set()

    for label, query in QUERIES:
        try:
            items = fetch_rss(query)
        except Exception as e:
            errors[label] = f"{type(e).__name__}: {e}"
            print(f"{label}: FAILED {e}", file=sys.stderr)
            continue
        kept = []
        for it in items:
            key = it["title"].lower()[:80]
            if not it["title"] or key in seen:
                continue
            seen.add(key)
            kept.append(it)
            if is_mover(it["title"]):
                movers.append({**it, "bucket": label})
        sections[label] = kept

    out = {"fetched_at": now, "movers": movers, "sections": sections, "errors": errors}
    NEWS_JSON.write_text(json.dumps(out, indent=2))

    lines = [f"# Market News Digest — {now}", ""]
    if movers:
        lines += ["## 🔴 MARKET MOVERS (react to these)", ""]
        for m in movers[:12]:
            lines.append(f"- **[{m['bucket']}]** {m['title']} — _{m['source']}_")
        lines.append("")
    for label, _ in QUERIES:
        items = sections.get(label) or []
        if not items:
            continue
        lines.append(f"## {label}")
        lines.append("")
        for it in items:
            lines.append(f"- {it['title']} — _{it['source']}_")
        lines.append("")
    if errors:
        lines += ["## Errors", ""] + [f"- {k}: {v}" for k, v in errors.items()]
    NEWS_MD.write_text("\n".join(lines) + "\n")

    print(f"news: {sum(len(v) for v in sections.values())} headlines, {len(movers)} movers at {now}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
