#!/usr/bin/env python3
"""OANDA v20 外汇经纪商适配器 — 与 broker_alpaca.py / broker_ai4trade.py 同一套接口。

为什么小账户选 OANDA:它按「单位(unit)」下单,1 单位起步,而不是 MT5 那种最小
0.01 手。对 $200 本金这不是偏好问题,是数学问题:

    46 点止损,想把风险控制在 1% ($2):
      MT5 最小 0.01 手 = $0.10/点 -> 46 点 = $4.60 = 本金的 2.3%   ← 超标
      OANDA 435 单位     = $0.0435/点 -> 46 点 = $2.00 = 本金的 1.0%  ← 正确

也就是说,在最小手数是 0.01 的平台上,$200 本金**根本无法**正确执行 1% 风险。
换平台是唯一解,不是调参能解决的。

API 文档: https://developer.oanda.com/rest-live-v20/introduction/
只用标准库(urllib),不引入 requests —— 和 broker_ai4trade.py 一样,少一个部署依赖。

环境变量(存 GitHub Actions secrets,别提交):
    OANDA_TOKEN        个人访问令牌
    OANDA_ACCOUNT_ID   形如 101-011-1234567-001
    OANDA_ENV          practice(默认,模拟盘) | live(真钱)

真钱双保险(照抄 broker_alpaca.py 的做法):
    OANDA_ENV=live 且 OANDA_I_UNDERSTAND_REAL_MONEY=yes 才会连真实账户。
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request

PRACTICE_HOST = "https://api-fxpractice.oanda.com/v3"
LIVE_HOST = "https://api-fxtrade.oanda.com/v3"

TOKEN = os.environ.get("OANDA_TOKEN", "").strip()
ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "").strip()
ENV = os.environ.get("OANDA_ENV", "practice").strip().lower()
TIMEOUT = float(os.environ.get("OANDA_TIMEOUT", "30"))

# 有 token + account 才算「可用」。缺任一项时上层走 dry-run,不会误下单。
OANDA_AVAILABLE = bool(TOKEN and ACCOUNT_ID)


class BrokerError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# 品种命名:OANDA 用 "EUR_USD"。允许上层传 "EURUSD" / "EUR/USD" / "eur_usd"。
# --------------------------------------------------------------------------
def normalize(symbol: str) -> str:
    s = str(symbol).upper().strip().replace("/", "_").replace("-", "_")
    if "_" not in s and len(s) == 6:
        s = f"{s[:3]}_{s[3:]}"
    return s


def pip_size(instrument: str) -> float:
    """一个 pip 的价格增量。JPY 计价的品种是 0.01,其余 0.0001。"""
    inst = normalize(instrument)
    return 0.01 if inst.endswith("_JPY") else 0.0001


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _host() -> str:
    return LIVE_HOST if ENV == "live" else PRACTICE_HOST


def _request(method: str, path: str, payload: dict | None = None, query: dict | None = None) -> dict:
    if not TOKEN:
        raise BrokerError("OANDA_TOKEN not set")
    url = f"{_host()}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept-Datetime-Format": "RFC3339",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:400]
        except Exception:
            pass
        raise BrokerError(f"{method} {path} -> HTTP {e.code} {detail}") from e
    except Exception as e:
        raise BrokerError(f"{method} {path} -> {e}") from e
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise BrokerError(f"{method} {path} -> non-JSON response: {body[:200]}")


class OandaBroker:
    """OANDA v20。接口与 AlpacaBroker 一致,另加外汇专用的 candles() /
    units_for_risk() / market_bracket()。

    qty 语义 = **单位数**,不是手数。正数做多,负数做空(外汇双向,和股票不同)。
    """

    def __init__(self) -> None:
        self.is_live = ENV == "live"
        self._acct = None

    # ---- lifecycle -------------------------------------------------------
    def connect(self) -> None:
        if not OANDA_AVAILABLE:
            raise BrokerError(
                "缺少 OANDA_TOKEN / OANDA_ACCOUNT_ID。到 oanda.com 开一个 "
                "practice(模拟)账户,在 Manage API Access 生成 token,"
                "然后设成环境变量(GitHub Actions: Settings -> Secrets)。"
            )
        if self.is_live:
            confirm = os.environ.get("OANDA_I_UNDERSTAND_REAL_MONEY", "no").lower()
            if confirm != "yes":
                raise BrokerError(
                    "真钱交易已被拦截。要用真实账户必须同时设置 "
                    "OANDA_ENV=live 和 OANDA_I_UNDERSTAND_REAL_MONEY=yes,"
                    "并使用 live(非 practice)的 token。"
                )
        # 拿一次账户摘要当鉴权自检:token/account 错在这里就炸,而不是等到下单。
        self._acct = _request("GET", f"/accounts/{ACCOUNT_ID}/summary").get("account", {})

    def disconnect(self) -> None:
        self._acct = None

    def __enter__(self) -> "OandaBroker":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()

    # ---- reads -----------------------------------------------------------
    def account(self) -> dict:
        a = self._acct or _request("GET", f"/accounts/{ACCOUNT_ID}/summary").get("account", {})
        nav = _f(a.get("NAV"), 0.0) or 0.0
        balance = _f(a.get("balance"), 0.0) or 0.0
        used = _f(a.get("marginUsed"), 0.0) or 0.0
        avail = _f(a.get("marginAvailable"), 0.0) or 0.0
        return {
            "cash": balance,
            "total_assets": nav,
            "equity": nav,
            "market_val": used,
            "power": avail,
            "status": (f"{'LIVE' if self.is_live else 'PRACTICE'} "
                       f"ccy={a.get('currency')} openTrades={a.get('openTradeCount')} "
                       f"unrealized={a.get('unrealizedPL')}"),
        }

    def positions(self) -> list:
        """净持仓。多头 qty 为正,空头为负 —— 外汇可以做空,别把负数当异常过滤掉。"""
        doc = _request("GET", f"/accounts/{ACCOUNT_ID}/openPositions")
        out = []
        for p in doc.get("positions", []) or []:
            inst = normalize(p.get("instrument", ""))
            long_u = _f((p.get("long") or {}).get("units"), 0.0) or 0.0
            short_u = _f((p.get("short") or {}).get("units"), 0.0) or 0.0
            qty = long_u + short_u          # short units 本身就是负数
            if abs(qty) <= 1e-9:
                continue
            side = p.get("long") if qty > 0 else p.get("short")
            entry = _f((side or {}).get("averagePrice"), 0.0) or 0.0
            unreal = _f((side or {}).get("unrealizedPL"), 0.0) or 0.0
            cost = abs(entry * qty)
            out.append({
                "symbol": inst,
                "qty": qty,
                "cost_price": entry,
                "market_val": cost,
                "pl_ratio": (unreal / cost) if cost else 0.0,
            })
        return out

    def _pricing(self, instrument: str) -> dict:
        inst = normalize(instrument)
        doc = _request("GET", f"/accounts/{ACCOUNT_ID}/pricing", query={"instruments": inst})
        prices = doc.get("prices", []) or []
        return prices[0] if prices else {}

    def price(self, symbol: str):
        """中间价(bid/ask 均值)。拿不到就返回 None,让上层回退到别的数据源。"""
        try:
            p = self._pricing(symbol)
            bid = _f((p.get("bids") or [{}])[0].get("price"))
            ask = _f((p.get("asks") or [{}])[0].get("price"))
            if bid is None or ask is None:
                return None
            return (bid + ask) / 2
        except Exception:
            return None

    def spread_pips(self, symbol: str):
        """点差(pip)。小账户必须盯这个:46 点止损 + 2 点差 = 实际风险多 4%。"""
        try:
            p = self._pricing(symbol)
            bid = _f((p.get("bids") or [{}])[0].get("price"))
            ask = _f((p.get("asks") or [{}])[0].get("price"))
            if bid is None or ask is None:
                return None
            return round((ask - bid) / pip_size(symbol), 2)
        except Exception:
            return None

    def is_market_open(self, symbol: str = "EUR_USD"):
        """外汇周末休市。OANDA 用 pricing 的 tradeable 标志告诉我们能不能交易。"""
        try:
            p = self._pricing(symbol)
            if not p:
                return None
            if "tradeable" in p:
                return bool(p.get("tradeable"))
            return str(p.get("status", "")).lower() == "tradeable"
        except Exception:
            return None

    def candles(self, symbol: str, granularity: str = "H4", count: int = 300,
                price: str = "M") -> list:
        """OHLC K 线。只返回 **已收盘** 的 K —— 未收盘那根的 close 会一直变,
        拿它算信号等于用未来函数,回测漂亮实盘打脸。"""
        inst = normalize(symbol)
        doc = _request("GET", f"/instruments/{inst}/candles", query={
            "granularity": granularity, "count": int(count), "price": price,
        })
        out = []
        for c in doc.get("candles", []) or []:
            if not c.get("complete"):
                continue
            mid = c.get("mid") or c.get("bid") or c.get("ask") or {}
            o, h, l, cl = (_f(mid.get("o")), _f(mid.get("h")),
                           _f(mid.get("l")), _f(mid.get("c")))
            if None in (o, h, l, cl):
                continue
            out.append({
                "time": c.get("time"), "o": o, "h": h, "l": l, "c": cl,
                "volume": c.get("volume", 0),
            })
        return out

    # ---- sizing ----------------------------------------------------------
    def units_for_risk(self, symbol: str, entry: float, stop: float,
                       risk_usd: float) -> int:
        """按「亏损金额固定」反推单位数 —— 这是整个小账户能否活下来的核心函数。

        units = 风险金额 / (止损距离(价格) * 每单位每价格点的报价货币价值)

        对 XXX_USD(报价货币是美元)的品种,每 1 单位每 1.0 价格变动 = 1 美元,
        所以直接除以止损距离即可。非美元计价的品种需要把报价货币换算成美元,
        换算不了就抛错 —— **宁可不下单,也不能按错误的规模下单**。
        """
        inst = normalize(symbol)
        dist = abs(float(entry) - float(stop))
        if dist <= 0:
            raise BrokerError("入场价与止损价相同,无法计算仓位")
        if risk_usd <= 0:
            raise BrokerError("风险金额必须为正")

        if inst.endswith("_USD"):
            quote_to_usd = 1.0
        else:
            quote_to_usd = self._quote_to_usd(inst)
            if quote_to_usd is None:
                raise BrokerError(
                    f"{inst} 的报价货币不是 USD,且拿不到换算汇率,拒绝下单"
                    "(错误的仓位规模比不交易危险得多)"
                )
        units = risk_usd / (dist * quote_to_usd)
        return int(units)     # 向下取整:宁可少冒一点风险

    def _quote_to_usd(self, instrument: str):
        """报价货币 -> USD 的汇率。先试 QUOTE_USD,再试 USD_QUOTE 取倒数。"""
        quote = normalize(instrument).split("_")[1]
        if quote == "USD":
            return 1.0
        for cand, invert in ((f"{quote}_USD", False), (f"USD_{quote}", True)):
            try:
                px = self.price(cand)
                if px:
                    return (1.0 / px) if invert else px
            except Exception:
                continue
        return None

    # ---- writes ----------------------------------------------------------
    def market_bracket(self, symbol: str, units: int, stop_loss: float = 0.0,
                       take_profit: float = 0.0):
        """市价单 + 附带止损/止盈。

        止损**必须**跟单子一起提交(stopLossOnFill),不能「先进场,回头再挂止损」——
        程序在两步之间崩掉、网络断掉、Actions runner 被回收,你就是一个裸单在市场里。
        """
        inst = normalize(symbol)
        units = int(units)
        if units == 0:
            raise BrokerError("units=0,不下单")
        digits = 3 if inst.endswith("_JPY") else 5
        order = {
            "type": "MARKET",
            "instrument": inst,
            "units": str(units),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
        }
        if stop_loss:
            order["stopLossOnFill"] = {"price": f"{float(stop_loss):.{digits}f}",
                                       "timeInForce": "GTC"}
        if take_profit:
            order["takeProfitOnFill"] = {"price": f"{float(take_profit):.{digits}f}",
                                         "timeInForce": "GTC"}
        resp = _request("POST", f"/accounts/{ACCOUNT_ID}/orders", {"order": order})
        # OANDA 拒单时照样返回 201,把拒绝原因塞在 orderRejectTransaction 里。
        # 不显式检查的话,上层会以为成交了,然后按幽灵仓位管理风险。
        if resp.get("orderRejectTransaction") or resp.get("orderCancelTransaction"):
            raise BrokerError(f"订单被拒: {json.dumps(resp)[:400]}")
        return resp

    def limit_bracket(self, symbol: str, units: int, price: float,
                      stop_loss: float = 0.0, take_profit: float = 0.0,
                      expiry_hours: float = 24.0):
        """限价单 + 附带止损/止盈。方案 A/B 的入场都是「回踩挂单」,不是市价追。

        带 GTD 到期时间:挂单没等到就自杀。一张挂了三天的单子等来的行情,
        和当初生成它的那根 K 线已经没有关系了 —— 那是过期的判断,不是耐心。
        """
        inst = normalize(symbol)
        units = int(units)
        if units == 0:
            raise BrokerError("units=0,不下单")
        digits = 3 if inst.endswith("_JPY") else 5
        expiry = (_dt.datetime.now(_dt.timezone.utc)
                  + _dt.timedelta(hours=float(expiry_hours)))
        order = {
            "type": "LIMIT",
            "instrument": inst,
            "units": str(units),
            "price": f"{float(price):.{digits}f}",
            "timeInForce": "GTD",
            "gtdTime": expiry.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "positionFill": "DEFAULT",
        }
        if stop_loss:
            order["stopLossOnFill"] = {"price": f"{float(stop_loss):.{digits}f}",
                                       "timeInForce": "GTC"}
        if take_profit:
            order["takeProfitOnFill"] = {"price": f"{float(take_profit):.{digits}f}",
                                         "timeInForce": "GTC"}
        resp = _request("POST", f"/accounts/{ACCOUNT_ID}/orders", {"order": order})
        if resp.get("orderRejectTransaction") or resp.get("orderCancelTransaction"):
            raise BrokerError(f"挂单被拒: {json.dumps(resp)[:400]}")
        return resp

    def orders(self) -> list:
        """未成交的挂单。"""
        doc = _request("GET", f"/accounts/{ACCOUNT_ID}/pendingOrders")
        out = []
        for o in doc.get("orders", []) or []:
            out.append({
                "id": str(o.get("id")),
                "type": o.get("type"),
                "symbol": normalize(o.get("instrument", "")),
                "units": _f(o.get("units"), 0.0),
                "price": _f(o.get("price")),
                "gtd": o.get("gtdTime"),
            })
        return out

    def order_state(self, order_id: str):
        """单张挂单的真实状态:PENDING / FILLED / CANCELLED / TRIGGERED。

        光看「它还在不在挂单列表里」是不够的 —— 一张成交后又被止盈平掉的单子,
        既不在挂单列表、也不在持仓里,会被误记成「到期未成交」。历史记录失真,
        事后复盘就会得出错误结论。
        """
        try:
            doc = _request("GET", f"/accounts/{ACCOUNT_ID}/orders/{order_id}")
            return str((doc.get("order") or {}).get("state", "")).upper() or None
        except Exception:
            return None

    def cancel_order(self, order_id: str):
        return _request("PUT", f"/accounts/{ACCOUNT_ID}/orders/{order_id}/cancel")

    def buy(self, symbol: str, qty: float, ref_price: float = 0.0):
        return self.market_bracket(symbol, abs(int(qty)))

    def sell(self, symbol: str, qty: float, ref_price: float = 0.0):
        return self.market_bracket(symbol, -abs(int(qty)))

    def close(self, symbol: str):
        """平掉该品种的全部仓位(多空都平)。已经是平的就直接返回,不重试幽灵平仓。"""
        inst = normalize(symbol)
        held = next((p for p in self.positions() if p["symbol"] == inst), None)
        if not held or abs(held["qty"]) <= 1e-9:
            return {"note": "already flat"}
        body = {"longUnits": "ALL"} if held["qty"] > 0 else {"shortUnits": "ALL"}
        return _request("PUT", f"/accounts/{ACCOUNT_ID}/positions/{inst}/close", body)


def describe_config() -> str:
    tok = f"{TOKEN[:6]}…{TOKEN[-4:]}" if len(TOKEN) > 12 else ("set" if TOKEN else "MISSING")
    acct = ACCOUNT_ID or "MISSING"
    return (f"OANDA | env={'LIVE(真钱)' if ENV == 'live' else 'PRACTICE(模拟)'} | "
            f"account={acct} | token={tok}")


if __name__ == "__main__":
    print(describe_config())
    if not OANDA_AVAILABLE:
        print("(未配置 token/account — 只做配置自检,不连接)")
    else:
        with OandaBroker() as b:
            print("account :", b.account())
            print("EUR_USD :", b.price("EUR_USD"), "spread(pips)=", b.spread_pips("EUR_USD"))
            print("open?   :", b.is_market_open("EUR_USD"))
            print("positions:", b.positions())
