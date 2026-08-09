#!/usr/bin/env python3
"""外汇 K 线数据源 — 免费、不需要券商账户。

为什么需要它:马来西亚开的 OANDA 账户会被分到 OANDA Global Markets(BVI),
而 OANDA 官方文档明写 v20 REST API「对所有分支开放,除了 OANDA Global Markets
和 OANDA TMS BROKERS」。也就是说那个地区拿不到 API —— 再注册多少次都一样。

所以行情和券商必须解耦:信号引擎用 Yahoo 免费行情自己算,你在自己的 MT5 上
手动执行。用哪家券商、有没有 API,都跟信号引擎没关系了。

Yahoo 没有 4 小时周期(只有 1h/1d 等),所以这里取 1h 再自己合成 H4。

⚠️ **H4 对齐方式**:本模块按 **UTC 00:00** 分桶(00/04/08/12/16/20 UTC)。
   你的 MT5 是按**券商服务器时间**对齐的,通常不是 UTC。两边的 H4 K 线因此会
   错位,阻力位可能差几个点。这不是 bug,是两套时间锚。要对齐就改 H4_ANCHOR_UTC。
"""

from __future__ import annotations

import json
import os
from urllib import request as urlrequest

# 和 quotes.py 用同一个 UA —— 那套请求已经在这个仓库的 Actions 上跑通过。
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)

H4_ANCHOR_UTC = int(os.environ.get("FOREX_H4_ANCHOR_UTC", "0"))  # 小时,0 = UTC 午夜
TIMEOUT = float(os.environ.get("FOREX_DATA_TIMEOUT", "30"))


def yahoo_symbol(instrument: str) -> str:
    """EUR_USD -> EURUSD=X。Yahoo 的外汇代码就是这个格式。"""
    return instrument.replace("_", "").replace("/", "").upper() + "=X"


def fetch_hourly(instrument: str, rng: str = "6mo") -> list:
    """从 Yahoo 取 1 小时 K 线。返回 [{ts,o,h,l,c,volume}...],按时间升序。

    6mo 的 1h 数据 ≈ 3000 根 ≈ 750 根 H4,足够算 EMA200(需要 200 根)。
    """
    sym = yahoo_symbol(instrument)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?range={rng}&interval=1h")
    req = urlrequest.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "application/json",
    })
    with urlrequest.urlopen(req, timeout=TIMEOUT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    result = payload["chart"]["result"][0]
    stamps = result.get("timestamp") or []
    q = (result.get("indicators", {}).get("quote") or [{}])[0]
    o, h, l, c = (q.get("open") or [], q.get("high") or [],
                  q.get("low") or [], q.get("close") or [])
    vol = q.get("volume") or []

    out = []
    for i, ts in enumerate(stamps):
        # Yahoo 会在数组里塞 null(停盘/缺数据)。带 None 的整根丢掉,
        # 不要用前值填充 —— 那是凭空造 K 线,指标会算在不存在的价格上。
        try:
            oo, hh, ll, cc = o[i], h[i], l[i], c[i]
        except IndexError:
            continue
        if None in (oo, hh, ll, cc):
            continue
        out.append({"ts": int(ts), "o": float(oo), "h": float(hh),
                    "l": float(ll), "c": float(cc),
                    "volume": int(vol[i]) if i < len(vol) and vol[i] else 0})
    out.sort(key=lambda x: x["ts"])
    return out


def resample_h4(hourly: list, now_ts: int | None = None) -> list:
    """1h -> 4h。按 UTC(可用 H4_ANCHOR_UTC 偏移)分桶。

    最后一个桶如果还没走完就丢掉 —— 用未收盘的 K 线算信号 = 未来函数。
    """
    import datetime as dt
    if not hourly:
        return []
    bucket_s = 4 * 3600
    anchor = H4_ANCHOR_UTC * 3600

    buckets = {}
    for bar in hourly:
        key = ((bar["ts"] - anchor) // bucket_s) * bucket_s + anchor
        b = buckets.get(key)
        if b is None:
            buckets[key] = {"ts": key, "o": bar["o"], "h": bar["h"],
                            "l": bar["l"], "c": bar["c"],
                            "volume": bar["volume"]}
        else:
            b["h"] = max(b["h"], bar["h"])
            b["l"] = min(b["l"], bar["l"])
            b["c"] = bar["c"]
            b["volume"] += bar["volume"]

    if now_ts is None:
        now_ts = int(dt.datetime.now(dt.timezone.utc).timestamp())

    out = []
    for key in sorted(buckets):
        if key + bucket_s > now_ts:
            continue                    # 这根还在形成中,丢掉
        b = buckets[key]
        out.append({
            "time": dt.datetime.fromtimestamp(b["ts"], dt.timezone.utc)
                      .isoformat(timespec="seconds").replace("+00:00", "Z"),
            "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"],
            "volume": b["volume"],
        })
    return out


def candles(instrument: str, granularity: str = "H4", count: int = 300) -> list:
    """给信号引擎用的统一入口,输出格式和 broker_oanda.candles() 一致。"""
    hourly = fetch_hourly(instrument)
    if granularity.upper() in ("H1", "1H"):
        import datetime as dt
        bars = [{"time": dt.datetime.fromtimestamp(b["ts"], dt.timezone.utc)
                          .isoformat(timespec="seconds").replace("+00:00", "Z"),
                 "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"],
                 "volume": b["volume"]} for b in hourly[:-1]]  # 丢掉未收盘那根
    else:
        bars = resample_h4(hourly)
    return bars[-count:]


if __name__ == "__main__":
    import sys
    inst = sys.argv[1] if len(sys.argv) > 1 else "EUR_USD"
    bars = candles(inst)
    print(f"{inst}: {len(bars)} 根 H4")
    for b in bars[-3:]:
        print(" ", b)
