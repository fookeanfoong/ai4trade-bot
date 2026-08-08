#!/usr/bin/env python3
"""
Alpaca CRYPTO broker adapter — the 24/7 twin of broker_alpaca.py.

Same broker surface (account / positions / price / buy / sell / close) so the
existing live_trader.py engine drives it unchanged. The differences vs stocks
are all crypto-specific and live here, not in the engine:

  * Symbols. The engine speaks BARE symbols ("BTC", "ETH"). Alpaca's crypto API
    wants a pair ("BTC/USD") for orders/data and reports positions as "BTCUSD".
    This adapter translates both ways so the rest of the system never sees a
    slash or a quote currency.
  * Market data. Crypto quotes come from CryptoHistoricalDataClient (public, no
    stock-data entitlement needed).
  * Time in force. Crypto market orders must be GTC (DAY is rejected).
  * Long only. Alpaca crypto has no shorting, so `sell` only ever reduces/closes
    an existing long — never opens a short. The engine keeps shorts off via
    ENABLE_SHORT=no on the crypto book.
  * Hours. Crypto is 24/7, so is_market_open() is always True.

Same account/keys as the stock adapter:
    ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY
    ALPACA_PAPER=true (default, fake money) | false (real, double-locked)

Install:  pip install -r requirements-alpaca.txt   (alpaca-py includes crypto)
"""

from __future__ import annotations

import os

try:
    from alpaca.trading.client import TradingClient           # type: ignore
    from alpaca.trading.requests import (MarketOrderRequest,     # type: ignore
                                        LimitOrderRequest,
                                        GetOrdersRequest)
    from alpaca.trading.enums import (OrderSide, TimeInForce,    # type: ignore
                                     QueryOrderStatus)
    from alpaca.data.historical import CryptoHistoricalDataClient  # type: ignore
    from alpaca.data.requests import CryptoLatestTradeRequest   # type: ignore
    ALPACA_AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - depends on host
    ALPACA_AVAILABLE = False
    _IMPORT_ERROR = e

# Quote currency Alpaca settles crypto in. USD pairs cover BTC/ETH/SOL/... .
QUOTE_CCY = os.environ.get("CRYPTO_QUOTE", "USD").upper()

# --- Maker vs taker ---------------------------------------------------------
# Alpaca crypto tier 1: 0.15% maker (resting limit) vs 0.25% taker (market).
# https://alpaca.markets/support/crypto-maker-taker-gmt-faq
#
# Live attribution says the signals are marginally positive GROSS (+$2.60) but
# fees were 3x that (-$7.74). Cutting the entry side to maker takes the round
# trip from 0.50% to 0.40% — a real dent in the dominant cost.
#
# ENTRIES ONLY. Exits stay market on purpose: a stop that does not fill is not a
# stop, and the whole point of the crash guard is that it gets you out. Saving
# 0.10% is never worth an exit that hangs.
#
# The trade-off maker orders carry is fill uncertainty and adverse selection —
# your buy rests, and it fills preferentially when the market is coming down at
# you. A missed entry costs nothing, so this is the safe side to take it on.
LIMIT_ENTRIES = os.environ.get("LIMIT_ENTRIES", "false").lower() in ("yes", "true")
# Offset from last price for the resting buy, as a fraction. 0 = at last (best
# fill odds); positive = below last (better price, fills less often).
LIMIT_OFFSET_PCT = float(os.environ.get("LIMIT_OFFSET_PCT", "0.0"))


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def to_pair(bare: str) -> str:
    """'BTC' -> 'BTC/USD'. Already-paired input passes through."""
    s = bare.upper()
    if "/" in s:
        return s
    if s.endswith(QUOTE_CCY) and len(s) > len(QUOTE_CCY):
        return f"{s[:-len(QUOTE_CCY)]}/{QUOTE_CCY}"
    return f"{s}/{QUOTE_CCY}"


def to_bare(symbol: str) -> str:
    """'BTC/USD' or 'BTCUSD' -> 'BTC'. Bare input passes through."""
    s = symbol.upper().replace("/", "")
    if s.endswith(QUOTE_CCY) and len(s) > len(QUOTE_CCY):
        return s[:-len(QUOTE_CCY)]
    return s


class BrokerError(RuntimeError):
    pass


class AlpacaCryptoBroker:
    """Crypto broker surface matching AlpacaBroker. The engine uses bare symbols
    ('BTC'); this class maps them to Alpaca pairs ('BTC/USD') internally."""

    def __init__(self) -> None:
        self.key = _env("ALPACA_API_KEY_ID")
        self.secret = _env("ALPACA_API_SECRET_KEY")
        self.paper = _env("ALPACA_PAPER", "true").lower() != "false"
        self.is_live = not self.paper
        self.client = None
        self.data = None

    # ---- lifecycle -------------------------------------------------------
    def connect(self) -> None:
        if not ALPACA_AVAILABLE:
            raise BrokerError(
                f"alpaca SDK not installed ({_IMPORT_ERROR}). "
                "Run: pip install -r requirements-alpaca.txt"
            )
        if not self.key or not self.secret:
            raise BrokerError(
                "Missing ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY. "
                "Create a free paper key at alpaca.markets and set them as env "
                "vars (GitHub Actions: repo Settings -> Secrets)."
            )
        if self.is_live:
            confirm = _env("ALPACA_I_UNDERSTAND_REAL_MONEY", "no").lower()
            if confirm != "yes":
                raise BrokerError(
                    "REAL trading blocked. To trade real money set "
                    "ALPACA_PAPER=false AND ALPACA_I_UNDERSTAND_REAL_MONEY=yes, "
                    "and use LIVE (not paper) API keys."
                )
        self.client = TradingClient(self.key, self.secret, paper=self.paper)
        # Crypto market data is public; keys are accepted but not required.
        self.data = CryptoHistoricalDataClient(self.key or None, self.secret or None)

    def disconnect(self) -> None:
        self.client = None
        self.data = None

    def __enter__(self) -> "AlpacaCryptoBroker":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()

    # ---- reads -----------------------------------------------------------
    def account(self) -> dict:
        a = self.client.get_account()

        def f(x):
            try:
                return float(x)
            except (TypeError, ValueError):
                return None
        return {
            "cash": f(a.cash),
            "total_assets": f(a.portfolio_value),
            "equity": f(a.equity),
            "market_val": f(a.long_market_value),
            "power": f(a.buying_power),
            "status": str(a.status),
        }

    def positions(self) -> list:
        """Crypto positions, symbols normalized to bare ('BTC')."""
        out = []
        for p in self.client.get_all_positions():
            # Only crypto positions belong to this book. asset_class may be an
            # enum or a string depending on SDK version.
            ac = str(getattr(p, "asset_class", "")).lower()
            if ac and "crypto" not in ac:
                continue
            qty = float(p.qty)
            out.append({
                "symbol": to_bare(p.symbol),
                "qty": qty,
                "cost_price": float(p.avg_entry_price),
                "market_val": float(p.market_value),
                "pl_ratio": float(p.unrealized_plpc),
            })
        return [p for p in out if abs(p["qty"]) > 1e-12]

    def price(self, symbol: str):
        """Latest crypto trade price, or None."""
        try:
            pair = to_pair(symbol)
            req = CryptoLatestTradeRequest(symbol_or_symbols=pair)
            res = self.data.get_crypto_latest_trade(req)
            return float(res[pair].price)
        except Exception:
            return None

    def is_market_open(self):
        # Crypto never closes.
        return True

    # ---- writes ----------------------------------------------------------
    def _market(self, symbol: str, side, qty: float):
        req = MarketOrderRequest(
            symbol=to_pair(symbol),
            qty=round(float(qty), 9),      # crypto allows fine fractional qty
            side=side,
            time_in_force=TimeInForce.GTC,  # crypto rejects DAY
        )
        return self.client.submit_order(req)

    def _limit(self, symbol: str, side, qty: float, price: float):
        req = LimitOrderRequest(
            symbol=to_pair(symbol),
            qty=round(float(qty), 9),
            side=side,
            limit_price=round(float(price), 9),
            time_in_force=TimeInForce.GTC,   # crypto rejects DAY
        )
        return self.client.submit_order(req)

    def cancel_stale_orders(self) -> int:
        """Cancel every open crypto order and return how many.

        Called at the top of each cycle. Resting limit entries that did not fill
        must not survive into the next cycle: the engine re-decides from scratch
        every run, and a stale order filling later would open a position nothing
        is managing. Cheap insurance — with nothing resting it is a no-op."""
        try:
            orders = self.client.get_orders(
                filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
        except Exception:
            return 0
        n = 0
        for o in orders:
            try:
                self.client.cancel_order_by_id(o.id)
                n += 1
            except Exception:
                pass
        return n

    def buy(self, symbol: str, qty: float, ref_price: float = 0.0):
        if LIMIT_ENTRIES and ref_price and ref_price > 0:
            return self._limit(symbol, OrderSide.BUY, qty,
                               ref_price * (1.0 - LIMIT_OFFSET_PCT))
        return self._market(symbol, OrderSide.BUY, qty)

    def sell(self, symbol: str, qty: float, ref_price: float = 0.0):
        # Long-only book: sell only reduces/closes an existing long.
        return self._market(symbol, OrderSide.SELL, qty)

    def close(self, symbol: str):
        """Liquidate the entire position for symbol.

        We do NOT use close_position(): Alpaca's DELETE /positions/{sym} endpoint
        is unreliable for crypto pairs ("BTC/USD" 404s with Not Found). Instead we
        market-SELL the exact held quantity via the same order path entries use
        (that path is proven to accept the pair format). If the broker turns out
        to be flat for this symbol, return cleanly so the caller drops its stale
        local plan instead of retrying a phantom close every run."""
        bare = to_bare(symbol)
        try:
            held = {to_bare(p.symbol): abs(float(p.qty))
                    for p in self.client.get_all_positions()}
        except Exception as e:
            raise BrokerError(f"positions() lookup for close {bare} failed: {e}")
        qty = held.get(bare, 0.0)
        if qty <= 1e-12:
            # Already flat on the broker — nothing to sell. Signal success so the
            # engine clears the stale local position (no infinite phantom-close).
            return {"status": "already_flat", "symbol": bare}
        return self._market(symbol, OrderSide.SELL, qty)


def describe_config() -> str:
    key = _env("ALPACA_API_KEY_ID")
    paper = _env("ALPACA_PAPER", "true").lower() != "false"
    sdk = "installed" if ALPACA_AVAILABLE else "NOT installed"
    have_keys = "set" if key else "MISSING"
    return (f"Alpaca CRYPTO | env={'PAPER' if paper else 'LIVE'} | quote={QUOTE_CCY} "
            f"| keys={have_keys} | sdk={sdk}")


if __name__ == "__main__":
    print(describe_config())
    if not ALPACA_AVAILABLE:
        print(f"(alpaca SDK import failed: {_IMPORT_ERROR})")
    else:
        for s in ("BTC", "ETH", "BTC/USD", "BTCUSD"):
            print(f"{s:8} -> pair {to_pair(s):10} bare {to_bare(s)}")
