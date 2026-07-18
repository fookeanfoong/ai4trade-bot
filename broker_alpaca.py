#!/usr/bin/env python3
"""
Alpaca broker adapter — same surface as broker_moomoo.py, but PURE CLOUD.

Why Alpaca is the default: it's a REST API with NO local gateway. Unlike Moomoo
(OpenD) or Interactive Brokers (IB Gateway), nothing has to stay running on a
machine you own. That means the paper (and later live) trader can run on GitHub
Actions on a schedule — your PC can be off. It also does fractional shares
(down to ~$1), so a small book can trade even $700 stocks.

Paper vs live:
  - Paper (ALPACA_PAPER=true, the default): paper-api.alpaca.markets, fake money.
    Create a paper key with just an email — no funding, no verification.
  - Live  (ALPACA_PAPER=false): api.alpaca.markets, REAL money. Double-locked
    behind ALPACA_I_UNDERSTAND_REAL_MONEY=yes so you can't flip by accident.

Credentials come from env (store as GitHub Actions secrets, never commit):
    ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY

The alpaca SDK is optional at import time so the repo/CI still work without it.
Install only where the trader runs:  pip install -r requirements-alpaca.txt
"""

from __future__ import annotations

import os

try:
    from alpaca.trading.client import TradingClient          # type: ignore
    from alpaca.trading.requests import MarketOrderRequest     # type: ignore
    from alpaca.trading.enums import OrderSide, TimeInForce    # type: ignore
    from alpaca.data.historical import StockHistoricalDataClient  # type: ignore
    from alpaca.data.requests import StockLatestTradeRequest   # type: ignore
    from alpaca.data.enums import DataFeed                     # type: ignore
    ALPACA_AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - depends on host
    ALPACA_AVAILABLE = False
    _IMPORT_ERROR = e


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


class BrokerError(RuntimeError):
    pass


class AlpacaBroker:
    """Minimal broker surface matching MoomooBroker: account, positions, price,
    buy/sell/close. Shares may be fractional. Symbols are bare ("SPY")."""

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
        self.data = StockHistoricalDataClient(self.key, self.secret)

    def disconnect(self) -> None:
        self.client = None
        self.data = None

    def __enter__(self) -> "AlpacaBroker":
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
        out = []
        for p in self.client.get_all_positions():
            qty = float(p.qty)  # Alpaca reports short qty as negative
            out.append({
                "symbol": p.symbol,
                "qty": qty,
                "cost_price": float(p.avg_entry_price),
                "market_val": float(p.market_value),
                "pl_ratio": float(p.unrealized_plpc),
            })
        return [p for p in out if abs(p["qty"]) > 1e-9]

    def price(self, symbol: str):
        """Latest trade price via the free IEX feed, or None."""
        try:
            req = StockLatestTradeRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
            res = self.data.get_stock_latest_trade(req)
            return float(res[symbol].price)
        except Exception:
            return None

    def is_market_open(self):
        try:
            return bool(self.client.get_clock().is_open)
        except Exception:
            return None

    # ---- writes ----------------------------------------------------------
    def _market(self, symbol: str, side, qty: float):
        req = MarketOrderRequest(
            symbol=symbol,
            qty=round(float(qty), 6),
            side=side,
            time_in_force=TimeInForce.DAY,  # fractional/notional must be DAY
        )
        return self.client.submit_order(req)

    def buy(self, symbol: str, qty: float, ref_price: float = 0.0):
        return self._market(symbol, OrderSide.BUY, qty)

    def sell(self, symbol: str, qty: float, ref_price: float = 0.0):
        return self._market(symbol, OrderSide.SELL, qty)

    def close(self, symbol: str):
        """Liquidate the entire position for symbol (robust full exit)."""
        try:
            return self.client.close_position(symbol)
        except Exception as e:
            raise BrokerError(f"close_position {symbol} failed: {e}")


def describe_config() -> str:
    key = _env("ALPACA_API_KEY_ID")
    paper = _env("ALPACA_PAPER", "true").lower() != "false"
    sdk = "installed" if ALPACA_AVAILABLE else "NOT installed"
    have_keys = "set" if key else "MISSING"
    return f"Alpaca | env={'PAPER' if paper else 'LIVE'} | keys={have_keys} | sdk={sdk}"


if __name__ == "__main__":
    print(describe_config())
    if not ALPACA_AVAILABLE:
        print(f"(alpaca SDK import failed: {_IMPORT_ERROR})")
