#!/usr/bin/env python3
"""
Daily market-mover news digest (freshness-enforced).

Runs on the GitHub Actions runner (has internet). Pulls headlines via free
Google News RSS for the people/events that move markets, then:
  - parses each headline's publish time
  - DROPS anything older than MAX_AGE_HOURS (default 24h)
  - sorts newest-first
  - shows a relative age ("2h ago") so staleness is obvious

Writes news.md (human digest) + news.json (machine-readable). A MOVERS
section highlights headlines mentioning key market-moving figures.

Note: direct Twitter/X access needs the paid API, so we don't read tweets
firsthand. Financial media report market-moving tweets within minutes, so
these keyword searches capture the market impact just as well.
"""

import datetime as dt
import email.utils as eut
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

MAX_AGE_HOURS = 24   # drop anything older than this — keep the digest fresh
PER_QUERY = 6

# (label, query). when:1d already limits Google News to the last day; the
# pubDate filter below is the hard guarantee.
QUERIES = [
    ("Market",   "US stock market today when:1d"),
    ("Trump",    "Trump stock market OR tariffs OR Iran when:1d"),
    ("Musk",     "Elon Musk Tesla when:1d"),
    ("Fed",      "Federal Reserve interest rates Powell when:1d"),
    ("Oil",      "oil price Iran OPEC Hormuz when:1d"),
    ("Chips",    "Nvidia AMD semiconductor stocks when:1d"),
    ("Earnings", "earnings today stock movers when:1d"),
]

MOVER_KEYWORDS = [
    "trump", "musk", "powell", "warsh", "fed", "federal reserve", "tariff",
    "iran", "opec", "hormuz", "ceasefire", "war", "strike", "sanction",
    "rate cut", "rate hike", "cpi", "inflation", "recession", "jobs report",
]


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def parse_pub(pub: str):
    if not pub:
        return None
    try:
        d = eut.parsedate_to_datetime(pub)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d
    except Exception:
        return None


def age_str(pub_dt, ref):
    if pub_dt is None:
        return "age?"
    mins = int((ref - pub_dt).total_seconds() // 60)
    if mins < 60:
        return f"{max(mins,0)}m ago"
    if mins < 60 * 24:
        return f"{mins // 60}h ago"
    return f"{mins // (60*24)}d ago"


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
        title = html.unescape(re.sub(r"<[^>]+>", "", it.findtext("title") or "")).strip()
        if not title:
            continue
        src_el = it.find("source")
        items.append({
            "title": title,
            "link": it.findtext("link") or "",
            "pub": it.findtext("pubDate") or "",
            "source": src_el.text if src_el is not None else "",
        })
    return items


def is_mover(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in MOVER_KEYWORDS)


def main() -> int:
    ref = now_utc()
    now_iso = ref.isoformat(timespec="seconds")
    cutoff = ref - dt.timedelta(hours=MAX_AGE_HOURS)

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
            pub_dt = parse_pub(it["pub"])
            # Hard freshness gate: drop stale. Keep undated (Google already
            # filtered to ~1d) but they sort last.
            if pub_dt is not None and pub_dt < cutoff:
                continue
            key = it["title"].lower()[:80]
            if key in seen:
                continue
            seen.add(key)
            it["age"] = age_str(pub_dt, ref)
            it["_sort"] = pub_dt.timestamp() if pub_dt else 0
            kept.append(it)
            if is_mover(it["title"]):
                movers.append({**it, "bucket": label})
        kept.sort(key=lambda x: x["_sort"], reverse=True)
        sections[label] = kept[:PER_QUERY]

    movers.sort(key=lambda x: x["_sort"], reverse=True)

    out = {"fetched_at": now_iso, "max_age_hours": MAX_AGE_HOURS,
           "movers": movers, "sections": sections, "errors": errors}
    NEWS_JSON.write_text(json.dumps(out, indent=2, default=str))

    lines = [
        f"# Market News Digest — {now_iso}",
        f"_Freshness: only headlines from the last {MAX_AGE_HOURS}h; newest first._",
        "",
    ]
    if movers:
        lines += ["## 🔴 MARKET MOVERS (react to these)", ""]
        for m in movers[:12]:
            lines.append(f"- `{m['age']}` **[{m['bucket']}]** {m['title']} — _{m['source']}_")
        lines.append("")
    for label, _ in QUERIES:
        items = sections.get(label) or []
        if not items:
            continue
        lines += [f"## {label}", ""]
        for it in items:
            lines.append(f"- `{it['age']}` {it['title']} — _{it['source']}_")
        lines.append("")
    if errors:
        lines += ["## Errors", ""] + [f"- {k}: {v}" for k, v in errors.items()]
    NEWS_MD.write_text("\n".join(lines) + "\n")

    total = sum(len(v) for v in sections.values())
    print(f"news: {total} fresh headlines (<{MAX_AGE_HOURS}h), {len(movers)} movers at {now_iso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
