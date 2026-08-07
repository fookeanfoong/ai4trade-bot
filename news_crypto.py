#!/usr/bin/env python3
"""加密市场的「暴跌新闻」哨兵 -> news_crypto.json。

价格护栏(generate_signals_crypto.py 里的 CRASH_* 阈值)看的是已经发生的下跌;
这个模块看的是**为什么**在跌。两者互补:

  - 新闻**永远不能单独停手或清仓**,只能让价格阈值提前生效。加密媒体每天都有
    负面标题,「有坏消息」不是可交易的信息;「坏消息 + 价格真的在跌」才是。

数据源用免费的 Google News RSS(和 news.py 同一套路,不需要 API key)。
只认「新鲜」新闻:超过 NEWS_MAX_AGE_HOURS 的一律忽略——三天前的黑客事件
不该让今天的机器人停手。

⚠️ 关键词匹配是启发式的,会有误判。所以默认的最重处罚也只是「暂停开新仓」,
   把清仓的决定权留给价格。
"""

import datetime as dt
import email.utils as eut
import html
import json
import os
import re
from pathlib import Path
from urllib import parse as urlparse
from urllib import request as urlrequest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "news_crypto.json"

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# 只看最近这么多小时的新闻。默认 6 小时:剥头皮的时间尺度是分钟,
# 一天前的消息早就反映在价格里了。
NEWS_MAX_AGE_HOURS = float(os.environ.get("NEWS_MAX_AGE_HOURS", "6"))
# 命中多少条「严重」新闻就进入 risk-off(暂停开新仓)。
NEWS_HALT_HITS = int(os.environ.get("NEWS_HALT_HITS", "3"))

QUERIES = [
    "bitcoin crash OR plunge OR selloff when:1d",
    "crypto exchange hack OR exploit OR stolen when:1d",
    "crypto withdrawals halted OR insolvency OR bankruptcy when:1d",
    "crypto ban OR crackdown OR SEC lawsuit when:1d",
    "ethereum OR solana OR xrp plunge OR liquidation when:1d",
]

# 严重词。第一版把 "hack"/"crash"/"plunge"/"liquidation"/"lawsuit"/"ban" 都算进来,
# 结果 6 小时内轻松命中 20+ 条,哨兵永久卡在告警状态——加密媒体每天都在用这些词,
# 连「Coldcard Hack Boosts Inflows to Bitcoin ETFs」(其实是利好)都被算成利空。
# 现在只保留「几乎不可能出现在中性报道里」的词组:
SEVERE = [
    "hacked for", "exploited for", "stolen funds", "funds drained",
    "insolvency", "insolvent", "bankruptcy", "files for chapter 11",
    "halts withdrawals", "withdrawals halted", "freezes withdrawals",
    "suspends withdrawals", "depeg", "depegs", "depegged",
    "flash crash", "capitulation", "exchange collapse", "ponzi",
    "trading halted", "emergency shutdown", "rug pull",
]


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def parse_pub(s: str):
    try:
        d = eut.parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def fetch_rss(query: str) -> list:
    url = ("https://news.google.com/rss/search?q="
           + urlparse.quote(query) + "&hl=en-US&gl=US&ceid=US:en")
    req = urlrequest.Request(url, headers={"User-Agent": BROWSER_UA})
    with urlrequest.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    out = []
    for it in root.iter("item"):
        title = html.unescape(re.sub(r"<[^>]+>", "", it.findtext("title") or "")).strip()
        if not title:
            continue
        out.append({"title": title, "pub": it.findtext("pubDate") or "",
                    "link": it.findtext("link") or ""})
    return out


def severity_of(title: str) -> list:
    t = title.lower()
    return [w for w in SEVERE if w in t]


def main() -> int:
    ref = now_utc()
    cutoff = ref - dt.timedelta(hours=NEWS_MAX_AGE_HOURS)
    seen, hits, errors = set(), [], {}

    for q in QUERIES:
        try:
            items = fetch_rss(q)
        except Exception as e:                      # 单个查询失败不该拖垮整轮
            errors[q] = str(e)[:160]
            continue
        for it in items:
            if it["title"] in seen:
                continue
            seen.add(it["title"])
            pub = parse_pub(it["pub"])
            if pub is None or pub < cutoff:         # 只认新鲜新闻
                continue
            words = severity_of(it["title"])
            if words:
                hits.append({"title": it["title"], "matched": words,
                             "published": pub.isoformat(timespec="seconds"),
                             "age_min": int((ref - pub).total_seconds() // 60),
                             "link": it["link"]})

    hits.sort(key=lambda h: h["age_min"])
    risk_off = len(hits) >= NEWS_HALT_HITS
    reason = ""
    if risk_off:
        top = "; ".join(h["title"][:90] for h in hits[:2])
        reason = (f"{len(hits)} 条 {NEWS_MAX_AGE_HOURS:g}h 内的重大负面新闻 "
                  f"(阈值 {NEWS_HALT_HITS}) — {top}")

    doc = {
        "updated_at": ref.isoformat(timespec="seconds"),
        "window_hours": NEWS_MAX_AGE_HOURS,
        "halt_threshold": NEWS_HALT_HITS,
        "hit_count": len(hits),
        "news_risk_off": risk_off,
        "reason": reason,
        "headlines": hits[:15],
        "errors": errors,
        # 全部查询都失败时标记出来:那不代表「没有坏消息」,只代表「没看到」。
        # 引擎看到这个标记会照常交易,但报告里会写明哨兵瞎了。
        "degraded": bool(errors) and not seen,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    if doc["degraded"]:
        print(f"wrote {OUT}: DEGRADED — every news query failed, guard is blind")
    elif risk_off:
        print(f"wrote {OUT}: NEWS RISK-OFF — {reason}")
    else:
        print(f"wrote {OUT}: {len(hits)} severe headline(s) in {NEWS_MAX_AGE_HOURS:g}h — clear")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
