#!/usr/bin/env python3
"""
Moomoo / Futu broker adapter — one thin wrapper around the official SDK.

This is the ONLY file that talks to the broker. Everything above it (the
signal-driven trader) is broker-agnostic, so swapping paper -> live is a
single env var (MOOMOO_TRD_ENV) and swapping brokers later means rewriting
only this file.

Architecture reality (read SETUP_MOOMOO.md):
  Your Python code does NOT connect to Moomoo's servers directly. It connects
  to **OpenD**, a gateway program that must be running + logged in on the SAME
  host (127.0.0.1:11111 by default). OpenD is what talks to Moomoo. That means
  this cannot run on GitHub Actions (ephemeral, no persistent login) — it runs
  on a machine that stays on (your PC or a small VPS).

Paper vs live:
  - Paper  (MOOMOO_TRD_ENV=SIMULATE, the default): fake money, NO unlock needed.
  - Live   (MOOMOO_TRD_ENV=REAL): real money, requires the trade password to
    unlock. We refuse to place live orders unless MOOMOO_TRADE_PWD is set AND
    MOOMOO_I_UNDERSTAND_REAL_MONEY=yes, so you can never flip to real by accident.

The moomoo SDK is optional at import time: if it isn't installed this module
still imports (MOOMOO_AVAILABLE = False) so the trader can run --dry-run and
the risk logic anywhere. Install it only on the host that runs OpenD:
    pip install -r requirements-moomoo.txt
"""

from __future__ import annotations

import os

# The SDK is only needed on the OpenD host. Guard the import so the rest of the
# repo (and CI) keeps working without it.
try:
    from moomoo import (  # type: ignore
        OpenSecTradeContext,
        OpenQuoteContext,
        TrdEnv,
        TrdSide,
        TrdMarket,
        OrderType,
        SecurityFirm,
        RET_OK,
    )
    MOOMOO_AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - depends on host
    MOOMOO_AVAILABLE = False
    _IMPORT_ERROR = e


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


class BrokerError(RuntimeError):
    pass


class MoomooBroker:
    """Minimal broker surface: account, positions, price, buy/sell, close.

    All quantities are in shares. US symbols are passed bare ("AAPL"); we add
    the "US." prefix the SDK expects. Prices are USD.
    """

    def __init__(self) -> None:
        self.host = _env("MOOMOO_HOST", "127.0.0.1")
        self.port = int(_env("MOOMOO_PORT", "11111"))
        env_name = _env("MOOMOO_TRD_ENV", "SIMULATE").upper()   # SIMULATE | REAL
        firm_name = _env("MOOMOO_SECURITY_FIRM", "FUTUINC")     # FUTUINC=US, set yours
        self.env_name = env_name
        self.firm_name = firm_name
        self.is_live = env_name == "REAL"
        self._trd = None
        self._quote = None

        if MOOMOO_AVAILABLE:
            self.trd_env = TrdEnv.REAL if self.is_live else TrdEnv.SIMULATE
            self.market = TrdMarket.US
            # Resolve the SecurityFirm enum by name so users on Moomoo MY / SG /
            # AU can set the right one without editing code.
            self.security_firm = getattr(SecurityFirm, firm_name, None)
            if self.security_firm is None:
                raise BrokerError(
                    f"Unknown MOOMOO_SECURITY_FIRM={firm_name!r}. "
                    "Common values: FUTUINC (US), FUTUSECURITIES (HK), "
                    "FUTUSG (Singapore), FUTUAU (Australia)."
                )
        else:
            self.trd_env = None
            self.market = None
            self.security_firm = None

    # ---- lifecycle -------------------------------------------------------
    def connect(self) -> None:
        if not MOOMOO_AVAILABLE:
            raise BrokerError(
                f"moomoo SDK not installed ({_IMPORT_ERROR}). "
                "On the OpenD host run: pip install -r requirements-moomoo.txt"
            )
        self._trd = OpenSecTradeContext(
            filter_trdmarket=self.market,
            host=self.host,
            port=self.port,
            security_firm=self.security_firm,
        )
        self._quote = OpenQuoteContext(host=self.host, port=self.port)

        if self.is_live:
            self._unlock_for_live()

    def _unlock_for_live(self) -> None:
        pwd = os.environ.get("MOOMOO_TRADE_PWD")
        confirm = _env("MOOMOO_I_UNDERSTAND_REAL_MONEY", "no").lower()
        if not pwd or confirm != "yes":
            raise BrokerError(
                "REAL trading blocked. To trade real money set BOTH "
                "MOOMOO_TRADE_PWD=<your trade password> and "
                "MOOMOO_I_UNDERSTAND_REAL_MONEY=yes. (Paper trading needs neither.)"
            )
        ret, data = self._trd.unlock_trade(pwd)
        if ret != RET_OK:
            raise BrokerError(f"unlock_trade failed: {data}")

    def disconnect(self) -> None:
        for ctx in (self._trd, self._quote):
            try:
                if ctx is not None:
                    ctx.close()
            except Exception:
                pass
        self._trd = self._quote = None

    def __enter__(self) -> "MoomooBroker":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()

    # ---- reads -----------------------------------------------------------
    def account(self) -> dict:
        """Return {cash, total_assets, market_val, power} for the active env."""
        ret, data = self._trd.accinfo_query(trd_env=self.trd_env)
        if ret != RET_OK:
            raise BrokerError(f"accinfo_query failed: {data}")
        row = data.iloc[0]

        def g(*names):
            for n in names:
                if n in data.columns:
                    return float(row[n])
            return None

        return {
            "cash": g("cash", "us_cash", "avl_withdrawal_cash"),
            "total_assets": g("total_assets"),
            "market_val": g("market_val"),
            "power": g("power", "max_power_short"),
        }

    def positions(self) -> list:
        """Open positions as [{symbol, qty, cost_price, market_val, pl_ratio}]."""
        ret, data = self._trd.position_list_query(trd_env=self.trd_env)
        if ret != RET_OK:
            raise BrokerError(f"position_list_query failed: {data}")
        out = []
        for _, r in data.iterrows():
            code = str(r.get("code", ""))
            out.append({
                "symbol": code.split(".")[-1],   # "US.AAPL" -> "AAPL"
                "qty": float(r.get("qty", 0) or 0),
                "cost_price": float(r.get("cost_price", 0) or 0),
                "market_val": float(r.get("market_val", 0) or 0),
                "pl_ratio": float(r.get("pl_ratio", 0) or 0),
            })
        return [p for p in out if abs(p["qty"]) > 1e-9]

    def price(self, symbol: str):
        """Last price from a market snapshot, or None if unavailable.

        Needs a US market-data quote right on the account; paper accounts often
        get delayed data, which is fine for our few-minute cadence. The trader
        falls back to quotes.json when this returns None.
        """
        code = f"US.{symbol}"
        ret, data = self._quote.get_market_snapshot([code])
        if ret != RET_OK or len(data) == 0:
            return None
        r = data.iloc[0]
        for col in ("last_price", "cur_price"):
            if col in data.columns and r[col] not in (None, 0):
                return float(r[col])
        return None

    # ---- writes ----------------------------------------------------------
    def _order(self, symbol: str, side, qty: float, ref_price: float):
        code = f"US.{symbol}"
        # Market order: price is a reference only (SDK still wants a number).
        ret, data = self._trd.place_order(
            price=float(ref_price or 0.0),
            qty=float(qty),
            code=code,
            trd_side=side,
            order_type=OrderType.MARKET,
            trd_env=self.trd_env,
        )
        if ret != RET_OK:
            raise BrokerError(f"place_order {side} {qty} {code} failed: {data}")
        return data

    def buy(self, symbol: str, qty: float, ref_price: float):
        return self._order(symbol, TrdSide.BUY, qty, ref_price)

    def sell(self, symbol: str, qty: float, ref_price: float):
        return self._order(symbol, TrdSide.SELL, qty, ref_price)


def describe_config() -> str:
    """One-line summary of how the adapter is configured (no secrets)."""
    host = _env("MOOMOO_HOST", "127.0.0.1")
    port = _env("MOOMOO_PORT", "11111")
    env_name = _env("MOOMOO_TRD_ENV", "SIMULATE").upper()
    firm = _env("MOOMOO_SECURITY_FIRM", "FUTUINC")
    sdk = "installed" if MOOMOO_AVAILABLE else "NOT installed"
    return f"OpenD {host}:{port} | env={env_name} | firm={firm} | market=US | sdk={sdk}"


if __name__ == "__main__":
    print(describe_config())
    if not MOOMOO_AVAILABLE:
        print(f"(moomoo SDK import failed: {_IMPORT_ERROR})")
