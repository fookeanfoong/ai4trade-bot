#!/usr/bin/env python3
"""外汇每日新闻简报 + 高影响事件封锁。

**关于「看新闻判断买升买跌」,先说清楚我能做什么、不能做什么:**

能做(而且已被验证有用):**用新闻做风险规避** —— CPI / 非农 / 央行决议前后,
汇价会在几秒内跳数十点。20 点止损在那种时候不是止损:价格**跳过去**,
成交价落在止损之外,20 点的风险变成实际亏 50 点。所以数据前后不开新仓。

不能做:**用新闻标题预测方向。** 没有可回测的历史标题库,就没有样本外验证。
一个未经验证的方向过滤器,加在一套本身还在验证中的规则上,
最可能的结果是把 edge 抹掉,而你会以为是新闻在帮忙。

关于推特:直接读 X/Twitter 需要付费 API,这里不读一手推文。
但真正能动市场的推文,财经媒体几分钟内就会报道 —— 下面的关键词搜索
抓的就是那个市场影响,效果一样(这个判断沿用仓库里 news.py 的做法)。

所以这个脚本产出两样东西:
  1. `news_gold.md` —— 给**你**读的简报(你自己判断方向,这是人的活)
  2. `gold_events.json` 的封锁窗口 —— 给**机器**用的,只管「什么时候别交易」

分工是故意的:机器负责它能被验证的部分,人负责它不能被验证的部分。

用法:python3 news_gold.py
"""

from __future__ import annotations

import datetime as dt
import email.utils as eut
import html
import json
import re
from pathlib import Path
from urllib import parse as urlparse
from urllib import request as urlrequest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT_MD = ROOT / "news_forex.md"
OUT_JSON = ROOT / "news_forex.json"

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
MAX_AGE_HOURS = 24
PER_QUERY = 5

# 外汇的驱动因素是**利率预期差**:各国央行的路径分歧决定汇率方向。
# 所以搜央行和通胀/就业数据,比搜"外汇行情"有用得多。
QUERIES = [
    ("美元", "US dollar index DXY forex"),
    ("美联储", "Federal Reserve interest rate decision Powell"),
    ("欧元/欧央行", "ECB euro interest rate decision"),
    ("英镑/英央行", "Bank of England pound sterling rate"),
    ("澳元/澳联储", "RBA Australian dollar interest rate"),
    ("通胀数据", "US CPI inflation report"),
    ("就业数据", "US nonfarm payrolls jobs report"),
]

# 命中这些词 = 当天有高影响事件,机器应该进入封锁。
# 只用于**风险规避**,不用于判断方向。
HIGH_IMPACT = [
    (r"\bCPI\b|inflation report|consumer price", "美国CPI"),
    (r"nonfarm|non-farm|payrolls|jobs report", "非农就业"),
    (r"\bFOMC\b|Fed decision|rate decision|Powell", "联储/FOMC"),
    (r"\bECB\b|European Central Bank", "欧央行"),
    (r"Bank of England|\bBoE\b", "英央行"),
    (r"\bRBA\b|Reserve Bank of Australia", "澳联储"),
    (r"\bPPI\b|producer price", "PPI"),
    (r"retail sales", "零售销售"),
]


def fetch_rss(query: str):
    url = ("https://news.google.com/rss/search?q="
           + urlparse.quote(query + " when:1d")
           + "&hl=en-US&gl=US&ceid=US:en")
    req = urlrequest.Request(url, headers={"User-Agent": BROWSER_UA})
    with urlrequest.urlopen(req, timeout=30) as r:
        return ET.fromstring(r.read())


def parse_items(root, limit=PER_QUERY):
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for item in root.iter("item"):
        title = html.unescape((item.findtext("title") or "").strip())
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate") or ""
        try:
            when = eut.parsedate_to_datetime(pub)
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt.timezone.utc)
        except Exception:
            continue
        age_h = (now - when).total_seconds() / 3600.0
        # 硬性时效:超过 24h 的直接丢。陈旧新闻比没有新闻更危险 ——
        # 它会让你以为自己掌握了现在的情况。
        if age_h > MAX_AGE_HOURS or age_h < -1:
            continue
        out.append({"title": title, "link": link,
                    "age_h": round(age_h, 1),
                    "when": when.isoformat(timespec="seconds")})
        if len(out) >= limit:
            break
    return out


def detect_events(all_items):
    hits = {}
    for it in all_items:
        for pat, label in HIGH_IMPACT:
            if re.search(pat, it["title"], re.I):
                hits.setdefault(label, []).append(it["title"])
    return hits


def main():
    now = dt.datetime.now(dt.timezone.utc)
    sections, all_items, errors = [], [], []

    for label, q in QUERIES:
        try:
            items = parse_items(fetch_rss(q))
        except Exception as e:
            errors.append(f"{label}: {e}")
            items = []
        sections.append((label, items))
        all_items.extend(items)

    events = detect_events(all_items)

    L = [f"# 外汇新闻简报 — {now:%Y-%m-%d %H:%M} UTC", ""]

    if events:
        L += ["## ⛔ 今日检测到高影响事件", ""]
        for label, titles in events.items():
            L.append(f"- **{label}** — {titles[0][:90]}")
        L += ["",
              "> **机器的动作:数据前后不开新仓。**",
              "> 20 点止损在数据发布时不是止损 —— 汇价几秒内跳数十点,",
              "> 成交价落在止损之外,20 点的风险会变成实际亏 50 点。",
              ""]
    else:
        L += ["## ✅ 今日未检测到高影响事件", "",
              "> 常规交易时段。注意这个检测基于新闻标题,不是官方日历 ——",
              "> 重要数据请以 ForexFactory 或你券商的日历为准。", ""]

    for label, items in sections:
        L.append(f"## {label}")
        L.append("")
        if not items:
            L += ["_24 小时内无新headline_", ""]
            continue
        for it in items:
            L.append(f"- ({it['age_h']}h前) [{it['title']}]({it['link']})")
        L.append("")

    L += ["---", "",
          "## 关于用新闻判断方向", "",
          "**这份简报是给你读的,不是给机器用的。**", "",
          "机器只从这里取一件事:**今天有没有高影响事件**(有就不开新仓)。",
          "它不会根据标题去判断做多还是做空 —— 那件事我没办法验证:",
          "没有可回测的历史标题数据,就没有样本外验证,",
          "而把一个未经验证的方向过滤器,叠在一套本身还在验证中的",
          "策略上,最可能的结果是把那点薄 edge 抹掉,你还会以为是新闻在帮忙。",
          "",
          "**分工是故意的**:机器负责能被验证的部分(什么时候别交易),",
          "人负责不能被验证的部分(方向判断)。", ""]

    if errors:
        L += ["> 取数失败:" + "；".join(errors), ""]

    OUT_MD.write_text("\n".join(L))
    OUT_JSON.write_text(json.dumps({
        "fetched_at": now.isoformat(timespec="seconds"),
        "high_impact_events": list(events.keys()),
        "blackout_recommended": bool(events),
        "items": all_items,
        "errors": errors,
    }, ensure_ascii=False, indent=2))

    print(f"[news-forex] {len(all_items)} 条 · 高影响事件 "
          f"{list(events.keys()) if events else '无'} · "
          f"建议封锁={'是' if events else '否'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
