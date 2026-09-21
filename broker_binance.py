#!/usr/bin/env python3
"""
Binance SPOT broker adapter — a third broker surface next to broker_alpaca*.py.

Same surface (account / positions / price / buy / sell / close / cancel_stale /
is_market_open) so the existing live_trader.py engine drives it UNCHANGED. Select
it with BROKER=binance. Everything Binance-specific lives here, not in the engine:

  * Symbols. The engine speaks BARE symbols ("ETH", "BTC"). Binance spot wants a
    pair ("ETHUSDT"). This adapter maps both ways (quote ccy = CRYPTO_QUOTE, USDT
    by default) so the rest of the system never sees a pair.
  * Spot has no "positions", only balances. We hold X ETH, not a position object.
    positions() synthesises positions from balances — see the BASELINE note below.
  * Testnet vs real. testnet.binance.vision (fake money) is the default; real
    money is double-locked behind BINANCE_I_UNDERSTAND_REAL_MONEY=yes, exactly
    like the Alpaca adapters.
  * Long only. Spot cannot short, so sell() only ever reduces/closes a long. The
    crypto signal layer already runs ENABLE_SHORT=no.
  * 24/7. is_market_open() is always True.
  * Prices come from the REAL public market (api.binance.com), never testnet — see
    the price() docstring for why. Only orders + balances route to testnet.

--- BASELINE: why positions() subtracts a snapshot -------------------------------
A Binance *testnet* account is pre-funded with large fake balances (e.g. 100 ETH,
1 BTC, 10000 USDT) that you never bought. If positions() reported raw balances,
the engine would think it already holds 100 ETH and, on exit, try to sell all of
it. So on first connect the runner writes `binance_baseline.json` = the balances
that exist BEFORE the bot trades. positions()/close() then report and unwind only
`current - baseline` — the net amount THIS BOT acquired. Preloaded testnet coins,
and on a real account any ETH you already hold, are invisible to the bot and never
sold. Re-snapshot (python broker_binance.py --snapshot-baseline) only if you
manually change balances. Missing file => baseline 0 (raw balances); the runner
creates it so that never happens by accident on a funded account.

Install:  pip install -r requirements-binance.txt
"""

from __future__ import annotations

import json
import os
import time
from decimal import Decimal, ROUND_DOWN

try:
    from binance.client import Client                       # type: ignore
    from binance.exceptions import (BinanceAPIException,       # type: ignore
                                    BinanceOrderException)
    BINANCE_AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - depends on host
    BINANCE_AVAILABLE = False
    _IMPORT_ERROR = e

# Quote currency Binance settles spot in. USDT covers ETH/BTC/SOL/... .
QUOTE_CCY = os.environ.get("CRYPTO_QUOTE", "USDT").upper()

# Where the "these balances are NOT bot positions" snapshot lives.
BASELINE_FILE = os.environ.get("BINANCE_BASELINE_FILE", "binance_baseline.json")

# Holdings worth less than this (valued at real price) are dust — ignored by
# positions() so a few cents of leftover coin never reads as an open position.
DUST_USD = float(os.environ.get("BINANCE_DUST_USD", "1.0"))


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def to_pair(bare: str) -> str:
    """'ETH' -> 'ETHUSDT'. Already-paired input passes through."""
    s = bare.upper().replace("/", "")
    if s.endswith(QUOTE_CCY) and len(s) > len(QUOTE_CCY):
        return s
    return f"{s}{QUOTE_CCY}"


def to_bare(symbol: str) -> str:
    """'ETHUSDT' or 'ETH/USDT' -> 'ETH'. Bare input passes through."""
    s = symbol.upper().replace("/", "")
    if s.endswith(QUOTE_CCY) and len(s) > len(QUOTE_CCY):
        return s[:-len(QUOTE_CCY)]
    return s


def _floor_step(qty: float, step: float) -> float:
    """Round a quantity DOWN to the symbol's LOT_SIZE step. Binance rejects any
    order whose qty is not a multiple of stepSize; rounding down (never up) also
    guarantees we never try to sell more than we hold."""
    if step <= 0:
        return float(qty)
    q = (Decimal(str(qty)) / Decimal(str(step))).to_integral_value(rounding=ROUND_DOWN)
    return float(q * Decimal(str(step)))


class BrokerError(RuntimeError):
    pass


class BinanceBroker:
    """Binance SPOT broker surface matching AlpacaCryptoBroker. Engine uses bare
    symbols ('ETH'); this class maps them to Binance pairs ('ETHUSDT')."""

    def __init__(self) -> None:
        self.key = _env("BINANCE_API_KEY")
        self.secret = _env("BINANCE_API_SECRET")
        # PAPER = Binance Spot Testnet (fake money). Default on.
        self.paper = _env("BINANCE_PAPER", "true").lower() != "false"
        self.is_live = not self.paper
        self.client = None        # orders + balances (testnet or real per paper)
        self._pub = None          # real public market data (price), always real
        self._filters: dict = {}  # pair -> {step, min_qty, min_notional}
        self._baseline: dict = {}

    # ---- lifecycle -------------------------------------------------------
    def connect(self) -> None:
        if not BINANCE_AVAILABLE:
            raise BrokerError(
                f"python-binance not installed ({_IMPORT_ERROR}). "
                "Run: pip install -r requirements-binance.txt"
            )
        if not self.key or not self.secret:
            where = "testnet.binance.vision" if self.paper else "binance.com"
            raise BrokerError(
                "Missing BINANCE_API_KEY / BINANCE_API_SECRET. Create a key at "
                f"{where} and set them as env vars (see SETUP_BINANCE.md)."
            )
        if self.is_live:
            confirm = _env("BINANCE_I_UNDERSTAND_REAL_MONEY", "no").lower()
            if confirm != "yes":
                raise BrokerError(
                    "REAL trading blocked. To trade real money set "
                    "BINANCE_PAPER=false AND BINANCE_I_UNDERSTAND_REAL_MONEY=yes, "
                    "and use REAL (not testnet) API keys."
                )
        # Orders/balances: testnet endpoint when paper, real otherwise.
        self.client = Client(self.key, self.secret, testnet=self.paper)
        # The real-market price feed (self._pub) is built lazily in price(), so a
        # transient hiccup on the public API never blocks the order/account path.
        # Binance rejects requests whose timestamp drifts outside recvWindow;
        # testnet clocks in particular skew. Pin our offset to server time.
        try:
            srv = self.client.get_server_time()["serverTime"]
            self.client.timestamp_offset = srv - int(time.time() * 1000)
        except Exception:
            pass
        self._load_baseline()

    def disconnect(self) -> None:
        self.client = None
        self._pub = None

    def __enter__(self) -> "BinanceBroker":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()

    # ---- baseline (see module docstring) --------------------------------
    def _load_baseline(self) -> None:
        try:
            with open(BASELINE_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._baseline = {k.upper(): float(v) for k, v in data.get("balances", data).items()}
        except Exception:
            self._baseline = {}

    def _raw_balances(self) -> dict:
        """{ASSET: free+locked} for every asset the account holds."""
        a = self.client.get_account()
        out = {}
        for b in a.get("balances", []):
            total = float(b.get("free", 0)) + float(b.get("locked", 0))
            if total > 0:
                out[b["asset"].upper()] = total
        return out

    def snapshot_baseline(self) -> dict:
        """Record current balances as the 'not a bot position' baseline and write
        it to BASELINE_FILE. Call once before the bot starts trading a fresh
        account (the runner does this automatically if the file is absent)."""
        bals = self._raw_balances()
        payload = {"taken_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "env": "TESTNET" if self.paper else "REAL",
                   "balances": bals}
        with open(BASELINE_FILE, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        self._baseline = bals
        return bals

    def _bot_qty(self, asset: str, total: float) -> float:
        """Amount of `asset` attributable to the bot = current total minus the
        pre-trade baseline, floored at 0. This is what positions()/close() act on
        so preloaded testnet funds (and your own pre-existing holdings) are never
        reported or sold."""
        return max(0.0, total - self._baseline.get(asset.upper(), 0.0))

    # ---- reads -----------------------------------------------------------
    def _free(self, asset: str) -> float:
        try:
            b = self.client.get_asset_balance(asset=asset.upper())
            return float(b["free"]) if b else 0.0
        except Exception:
            return 0.0

    def account(self) -> dict:
        a = self.client.get_account()
        free_q = 0.0
        total_q = 0.0
        mv = 0.0
        for b in a.get("balances", []):
            asset = b["asset"].upper()
            free = float(b.get("free", 0))
            total = free + float(b.get("locked", 0))
            if total <= 0:
                continue
            if asset == QUOTE_CCY:
                free_q += free
                total_q += total
                continue
            px = self.price(asset)
            if px:
                mv += total * px
        equity = total_q + mv
        return {
            "cash": free_q,
            "total_assets": equity,
            "equity": equity,
            "market_val": mv,
            "power": free_q,          # spot: buying power = free quote balance
            "status": "ACTIVE" + (" (TESTNET)" if self.paper else ""),
        }

    def positions(self) -> list:
        """Bot-attributable spot holdings (current - baseline), bare symbols."""
        out = []
        for asset, total in self._raw_balances().items():
            if asset == QUOTE_CCY:
                continue
            qty = self._bot_qty(asset, total)
            if qty <= 0:
                continue
            px = self.price(asset)
            if px is None:
                continue
            mv = qty * px
            if mv < DUST_USD:
                continue
            out.append({
                "symbol": asset,
                "qty": qty,
                "cost_price": px,     # spot API has no avg entry; engine uses its own
                "market_val": mv,
                "pl_ratio": 0.0,
            })
        return out

    def price(self, symbol: str):
        """Latest REAL-market trade price for the bare symbol, or None.

        Always the real public market, even on testnet. The signal layer builds
        setups from real market data (quotes_crypto.py / Yahoo), so stop/target
        management MUST track that same real market — otherwise testnet's thin,
        stale book would trip phantom stops. On testnet only the ORDERS execute
        against fake liquidity; the strategy sees the real ETH price throughout."""
        try:
            if self._pub is None:
                self._pub = Client()          # keyless real-market client (lazy)
            pair = to_pair(symbol)
            t = self._pub.get_symbol_ticker(symbol=pair)
            return float(t["price"])
        except Exception:
            self._pub = None                  # allow a rebuild next call
            return None

    def is_market_open(self):
        return True  # crypto never closes

    # ---- filters ---------------------------------------------------------
    def _symbol_filters(self, pair: str) -> dict:
        if pair in self._filters:
            return self._filters[pair]
        f = {"step": 0.0, "min_qty": 0.0, "min_notional": 0.0}
        try:
            info = self.client.get_symbol_info(pair)
            for filt in (info or {}).get("filters", []):
                t = filt.get("filterType")
                if t == "LOT_SIZE":
                    f["step"] = float(filt.get("stepSize", 0) or 0)
                    f["min_qty"] = float(filt.get("minQty", 0) or 0)
                elif t in ("MIN_NOTIONAL", "NOTIONAL"):
                    f["min_notional"] = float(
                        filt.get("minNotional", filt.get("notional", 0)) or 0)
        except Exception:
            pass
        self._filters[pair] = f
        return f

    def _prep_qty(self, pair: str, qty: float, ref_price: float) -> float:
        """Floor to LOT_SIZE and validate against minQty / minNotional. Raises
        BrokerError (which the engine logs as ORDER FAILED and skips) if the order
        is too small to be legal."""
        f = self._symbol_filters(pair)
        q = _floor_step(qty, f["step"]) if f["step"] else float(qty)
        if q <= 0 or (f["min_qty"] and q < f["min_qty"]):
            raise BrokerError(
                f"{pair}: qty {qty:g} rounds to {q:g}, below minQty {f['min_qty']:g}")
        px = ref_price or self.price(to_bare(pair)) or 0.0
        if f["min_notional"] and px and q * px < f["min_notional"]:
            raise BrokerError(
                f"{pair}: notional ${q * px:.2f} below Binance min "
                f"${f['min_notional']:.2f} — raise the slice or trade fewer names")
        return q

    # ---- writes ----------------------------------------------------------
    def cancel_stale_orders(self) -> int:
        """Cancel every resting open order and return how many. This book places
        only MARKET orders, so normally a no-op — cheap insurance against a
        resting order left by a manual action or a past config."""
        n = 0
        try:
            for o in self.client.get_open_orders():
                try:
                    self.client.cancel_order(symbol=o["symbol"], orderId=o["orderId"])
                    n += 1
                except Exception:
                    pass
        except Exception:
            return 0
        return n

    def buy(self, symbol: str, qty: float, ref_price: float = 0.0):
        pair = to_pair(symbol)
        q = self._prep_qty(pair, qty, ref_price)
        try:
            return self.client.order_market_buy(symbol=pair, quantity=q)
        except (BinanceAPIException, BinanceOrderException) as e:
            raise BrokerError(f"buy {pair} x{q:g} failed: {e}")

    def sell(self, symbol: str, qty: float, ref_price: float = 0.0):
        """Long-only book: reduce/close a long. Never sells more than the free
        balance, and never below the baseline (your own coins stay untouched)."""
        pair = to_pair(symbol)
        bare = to_bare(pair)
        free = self._free(bare)
        sellable = min(float(qty), free, self._bot_qty(bare, self._raw_balances().get(bare, 0.0)))
        q = _floor_step(sellable, self._symbol_filters(pair)["step"])
        if q <= 0:
            raise BrokerError(f"sell {pair}: nothing bot-attributable to sell")
        try:
            return self.client.order_market_sell(symbol=pair, quantity=q)
        except (BinanceAPIException, BinanceOrderException) as e:
            raise BrokerError(f"sell {pair} x{q:g} failed: {e}")

    def close(self, symbol: str):
        """Liquidate the bot's entire position in symbol at market.

        Sells `current - baseline` (bot-acquired amount), capped at the free
        balance and floored to LOT_SIZE — so it unwinds exactly what the bot
        bought and never the preloaded/your-own coins. Returns cleanly if already
        flat so the engine drops its stale local plan instead of looping."""
        pair = to_pair(symbol)
        bare = to_bare(pair)
        totals = self._raw_balances()
        qty = min(self._bot_qty(bare, totals.get(bare, 0.0)), self._free(bare))
        q = _floor_step(qty, self._symbol_filters(pair)["step"])
        if q <= 0:
            return {"status": "already_flat", "symbol": bare}
        try:
            return self.client.order_market_sell(symbol=pair, quantity=q)
        except (BinanceAPIException, BinanceOrderException) as e:
            raise BrokerError(f"close {pair} x{q:g} failed: {e}")


def describe_config() -> str:
    key = _env("BINANCE_API_KEY")
    paper = _env("BINANCE_PAPER", "true").lower() != "false"
    sdk = "installed" if BINANCE_AVAILABLE else "NOT installed"
    have_keys = "set" if key else "MISSING"
    base = "TESTNET" if paper else "LIVE"
    have_base = "yes" if os.path.exists(BASELINE_FILE) else "no"
    return (f"Binance SPOT | env={base} | quote={QUOTE_CCY} | keys={have_keys} "
            f"| sdk={sdk} | baseline={have_base}")


if __name__ == "__main__":
    import sys
    if "--snapshot-baseline" in sys.argv:
        b = BinanceBroker()
        b.connect()
        bals = b.snapshot_baseline()
        print(f"baseline written to {BASELINE_FILE} ({'TESTNET' if b.paper else 'REAL'}):")
        for k, v in sorted(bals.items()):
            print(f"  {k:6} {v:g}")
        b.disconnect()
    else:
        print(describe_config())
        if not BINANCE_AVAILABLE:
            print(f"(python-binance import failed: {_IMPORT_ERROR})")
        else:
            for s in ("ETH", "BTC", "ETHUSDT", "ETH/USDT"):
                print(f"{s:9} -> pair {to_pair(s):10} bare {to_bare(s)}")
