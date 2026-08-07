#!/usr/bin/env python3
"""AI-Trader (ai4trade.ai) broker adapter — same interface as the Alpaca ones.

把 ai4trade.ai 当成一个「券商」来用:下单 = 发布 realtime signal,持仓/现金
直接读平台的账本。live_trader.py 不需要任何改动,BROKER=ai4trade 即可切换。

⚠️ 这个平台是**模拟盘**:注册送 $100,000 虚拟资金,没有真实撮合、没有真钱。
   它同时是个社交平台——你的每一笔「交易」都会公开发布成信号,别人能看到、能跟单。
   这跟 Alpaca 纸上账户的性质不同:Alpaca 走真实订单路径,改个开关就是真钱;
   这里不行。

API(来自 https://ai4trade.ai/skill/ai4trade):
  GET  /api/claw/agents/me      -> 账号信息 + cash
  GET  /api/positions           -> 持仓
  POST /api/signals/realtime    -> 下单(同时公开发布)

只用标准库(urllib),不引入 requests,免得多一个部署依赖。
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("AI4TRADE_BASE", "https://ai4trade.ai/api").rstrip("/")
TOKEN = os.environ.get("AI4TRADE_TOKEN", "").strip()
MARKET = os.environ.get("AI4TRADE_MARKET", "crypto")
TIMEOUT = float(os.environ.get("AI4TRADE_TIMEOUT", "30"))
# 下单价:默认报我们自己算出来的参考价(skill 里的 Method 1「同步外部交易」),
# 这样平台记录的成交价和我们本地的止损/目标算在同一个价位上。
# 设成 yes 则改用 Method 2:price=0 + executed_at="now",由平台自己查价——
# 平台价和本地价会有偏差,止损/目标就可能对不齐,所以不是默认。
USE_PLATFORM_PRICE = os.environ.get("AI4TRADE_PLATFORM_PRICE", "no").lower() in ("yes", "true")

# 有 token 才算「可用」。没有 token 时 live_trader 会走 dry-run,不会误下单。
AI4TRADE_AVAILABLE = bool(TOKEN)


class BrokerError(RuntimeError):
    pass


def describe_config() -> str:
    tok = f"{TOKEN[:6]}…{TOKEN[-4:]}" if len(TOKEN) > 12 else ("set" if TOKEN else "MISSING")
    return (f"broker=ai4trade (SIMULATED) base={BASE_URL} market={MARKET} "
            f"token={tok} price_source={'platform' if USE_PLATFORM_PRICE else 'local'}")


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    """调用平台 API。非 2xx 一律抛 BrokerError,让上层的 _send() 记录失败并保持
    本地状态不变——绝不能在下单失败的情况下让引擎以为自己成交了。"""
    if not TOKEN:
        raise BrokerError("AI4TRADE_TOKEN not set")
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
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


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


class AI4TradeBroker:
    """ai4trade.ai 模拟盘。接口与 AlpacaCryptoBroker 一致。"""

    def __init__(self) -> None:
        self._me = None

    # ---- lifecycle -------------------------------------------------------
    def connect(self) -> None:
        # 拿一次账号信息当作鉴权自检:token 无效在这里就炸,而不是等到下单。
        self._me = _request("GET", "/claw/agents/me")

    def disconnect(self) -> None:
        self._me = None

    def __enter__(self) -> "AI4TradeBroker":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()

    # ---- reads -----------------------------------------------------------
    def account(self) -> dict:
        me = self._me or _request("GET", "/claw/agents/me")
        cash = _f(me.get("cash"), 0.0)
        held = sum(abs(_f(p.get("market_val"), 0.0) or 0.0) for p in self.positions())
        return {
            "cash": cash,
            "total_assets": cash + held,
            "equity": cash + held,
            "market_val": held,
            "power": cash,
            "status": f"SIMULATED points={me.get('points')} rep={me.get('reputation_score')}",
        }

    def positions(self) -> list:
        """本账号的持仓。跟单来的仓位(source='copied:*')不归这个引擎管,过滤掉——
        否则 reconcile() 会把别人的仓位当成我们自己的,进而去平掉它。"""
        doc = _request("GET", "/positions")
        out = []
        for p in doc.get("positions", []) or []:
            src = str(p.get("source", "self") or "self")
            if src.startswith("copied"):
                continue
            qty = _f(p.get("quantity"), 0.0) or 0.0
            entry = _f(p.get("entry_price"), 0.0) or 0.0
            cur = _f(p.get("current_price"), entry) or entry
            pnl = _f(p.get("pnl"), 0.0) or 0.0
            cost = entry * qty
            out.append({
                "symbol": str(p.get("symbol", "")).upper(),
                "qty": qty,
                "cost_price": entry,
                "market_val": cur * qty,
                "pl_ratio": (pnl / cost) if cost else 0.0,
            })
        return [p for p in out if abs(p["qty"]) > 1e-12]

    def price(self, symbol: str):
        """平台没有公开的报价端点。返回 None,让 live_trader 回退到
        quotes_crypto.json(Yahoo 5m 行情)——那本来就是信号层用的同一份数据。"""
        return None

    def is_market_open(self):
        return True   # 加密 24/7;平台也不设开市时间

    # ---- writes ----------------------------------------------------------
    def _realtime(self, action: str, symbol: str, qty: float, ref_price: float) -> dict:
        body = {
            "market": MARKET,
            "action": action,
            "symbol": str(symbol).upper(),
            "quantity": round(float(qty), 9),
            "content": f"ai4trade-bot {action} {symbol}",
        }
        if USE_PLATFORM_PRICE or not ref_price or ref_price <= 0:
            body["price"] = 0
            body["executed_at"] = "now"
        else:
            body["price"] = float(ref_price)
            # 必须带 Z。skill 文档的示例("2026-03-05T12:00:00")是错的,真实 API 会回
            # 400: "executed_at must be in UTC format (ending with Z or +00:00)"。
            body["executed_at"] = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        resp = _request("POST", "/signals/realtime", body)
        if resp.get("success") is False:
            raise BrokerError(f"realtime {action} {symbol} rejected: {resp}")
        return resp

    def buy(self, symbol: str, qty: float, ref_price: float = 0.0):
        return self._realtime("buy", symbol, qty, ref_price)

    def sell(self, symbol: str, qty: float, ref_price: float = 0.0):
        return self._realtime("sell", symbol, qty, ref_price)

    def close(self, symbol: str):
        """平掉整个仓位。平台没有「一键平仓」端点,所以先读实际持仓数量再市价卖出。
        平台已经是平的就直接返回,让上层丢掉本地的陈旧计划,而不是每轮重试幽灵平仓。"""
        bare = str(symbol).upper()
        held = next((p for p in self.positions() if p["symbol"] == bare), None)
        if not held or abs(held["qty"]) <= 1e-12:
            return {"success": True, "note": "already flat on platform"}
        return self._realtime("sell", bare, abs(held["qty"]), held["cost_price"])
