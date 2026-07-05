#!/usr/bin/env python3
"""
trading_bot_guardrails
======================

Safety layer for the sim-trading bot.  Public API:

    can_open_new_position(symbol, account_value, num_open_positions) -> bool
    calculate_position_size(account_value, entry_price, stop_price)  -> float qty
    validate_order(symbol, side, qty, price, account_value)          -> bool
    log_trade(symbol, side, qty, price, reason)                      -> None
    should_stop_loss(symbol, side, entry_price, current_price)       -> bool
    should_take_profit(symbol, side, entry_price, current_price)     -> bool
    log_position_closed(symbol, side, qty, entry, exit, pnl_usd, reason)

Kill switch: create `KILL_SWITCH.txt` in this folder to block ALL new orders.
Daily loss limit: once realised loss today >= DAILY_LOSS_LIMIT_PCT of account,
                  no new positions until next NY calendar day.

Standalone run (`python trading_bot_guardrails.py`) prints CONFIG so you can
sanity-check installation.
"""

import csv
import datetime as dt
import json
import os
from pathlib import Path

try:
    import pytz
except ImportError as e:
    raise SystemExit("pytz missing.  run: pip install pytz") from e

HERE = Path(__file__).resolve().parent

# ============================================================================
# CONFIG  -- edit these values, do not touch the code below.
# ============================================================================
CONFIG = {
    "ALLOWED_SYMBOLS":         ["AMD", "PLTR", "MSTR", "AVGO", "COIN"],
    "MAX_POSITIONS":           5,
    "STOP_LOSS_PCT":           0.02,   # 2%   -- day traders ~1%, swing 3-5%
    "TAKE_PROFIT_PCT":         0.04,   # 2x stop  = positive risk/reward
    "DAILY_LOSS_LIMIT_PCT":    0.03,   # 3% of account  -> halt for the day
    "MAX_RISK_PER_TRADE_PCT":  0.01,   # 1% of account risked per trade
    "MIN_ORDER_USD":           1.00,
    "MAX_ORDER_USD":           25.00,  # hard cap so risk sizing cannot over-leverage
    "TRADING_HOURS_TZ":        "America/New_York",
    "TRADING_START":           "09:30",
    "TRADING_END":             "16:00",
    "KILL_SWITCH_FILE":        str(HERE / "KILL_SWITCH.txt"),
    "TRADE_LOG_FILE":          str(HERE / "guardrails_trades.csv"),
    "DAILY_STATE_FILE":        str(HERE / "guardrails_daily.json"),
}
# ============================================================================


# ---- helpers ---------------------------------------------------------------

def _ny_now():
    return dt.datetime.now(pytz.timezone(CONFIG["TRADING_HOURS_TZ"]))


def _within_trading_hours():
    n = _ny_now()
    if n.weekday() >= 5:
        return False
    start_h, start_m = [int(x) for x in CONFIG["TRADING_START"].split(":")]
    end_h,   end_m   = [int(x) for x in CONFIG["TRADING_END"].split(":")]
    cur = n.hour * 60 + n.minute
    return (start_h * 60 + start_m) <= cur <= (end_h * 60 + end_m)


def _kill_switch_active():
    return Path(CONFIG["KILL_SWITCH_FILE"]).exists()


def _load_daily():
    p = Path(CONFIG["DAILY_STATE_FILE"])
    if not p.exists():
        return {"date": "", "realised_pnl": 0.0}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"date": "", "realised_pnl": 0.0}


def _save_daily(state):
    Path(CONFIG["DAILY_STATE_FILE"]).write_text(
        json.dumps(state, indent=2), encoding="utf-8")


def _bump_daily_pnl(pnl_usd):
    today = _ny_now().strftime("%Y-%m-%d")
    st = _load_daily()
    if st["date"] != today:
        st = {"date": today, "realised_pnl": 0.0}
    st["realised_pnl"] += pnl_usd
    _save_daily(st)


def _daily_loss_hit(account_value):
    today = _ny_now().strftime("%Y-%m-%d")
    st = _load_daily()
    if st["date"] != today:
        return False
    limit = -CONFIG["DAILY_LOSS_LIMIT_PCT"] * account_value
    return st["realised_pnl"] <= limit


# ---- public API ------------------------------------------------------------

def can_open_new_position(symbol, account_value, num_open_positions):
    if _kill_switch_active():
        print(f"[gr] kill switch active -> block {symbol}")
        return False
    if symbol not in CONFIG["ALLOWED_SYMBOLS"]:
        print(f"[gr] {symbol} not in ALLOWED_SYMBOLS -> block")
        return False
    if num_open_positions >= CONFIG["MAX_POSITIONS"]:
        print(f"[gr] MAX_POSITIONS ({CONFIG['MAX_POSITIONS']}) reached -> block {symbol}")
        return False
    if not _within_trading_hours():
        print(f"[gr] outside trading hours -> block {symbol}")
        return False
    if _daily_loss_hit(account_value):
        print(f"[gr] daily loss limit hit -> block {symbol}")
        return False
    return True


def calculate_position_size(account_value, entry_price, stop_price):
    if entry_price <= 0 or stop_price <= 0:
        return 0.0
    risk_per_share = abs(entry_price - stop_price)
    if risk_per_share <= 0:
        return 0.0
    dollars_at_risk = account_value * CONFIG["MAX_RISK_PER_TRADE_PCT"]
    qty = dollars_at_risk / risk_per_share
    notional = qty * entry_price
    if notional > CONFIG["MAX_ORDER_USD"]:
        qty = CONFIG["MAX_ORDER_USD"] / entry_price
    if qty * entry_price < CONFIG["MIN_ORDER_USD"]:
        return 0.0
    return qty


def validate_order(symbol, side, qty, price, account_value):
    if _kill_switch_active():
        print(f"[gr] kill switch active -> reject order")
        return False
    if symbol not in CONFIG["ALLOWED_SYMBOLS"]:
        print(f"[gr] {symbol} not allowed -> reject")
        return False
    if side not in ("buy", "sell"):
        print(f"[gr] bad side {side!r} -> reject")
        return False
    if qty <= 0 or price <= 0:
        print(f"[gr] non-positive qty/price -> reject")
        return False
    notional = qty * price
    if notional < CONFIG["MIN_ORDER_USD"]:
        print(f"[gr] notional ${notional:.2f} < MIN_ORDER_USD -> reject")
        return False
    if notional > CONFIG["MAX_ORDER_USD"] + 1e-6:
        print(f"[gr] notional ${notional:.2f} > MAX_ORDER_USD -> reject")
        return False
    if side == "buy" and notional > account_value + 1e-6:
        print(f"[gr] notional exceeds account_value -> reject")
        return False
    return True


def should_stop_loss(symbol, side, entry_price, current_price):
    if entry_price <= 0 or current_price <= 0:
        return False
    move = (current_price - entry_price) / entry_price
    if side == "buy":
        return move <= -CONFIG["STOP_LOSS_PCT"]
    return move >= CONFIG["STOP_LOSS_PCT"]


def should_take_profit(symbol, side, entry_price, current_price):
    if entry_price <= 0 or current_price <= 0:
        return False
    move = (current_price - entry_price) / entry_price
    if side == "buy":
        return move >= CONFIG["TAKE_PROFIT_PCT"]
    return move <= -CONFIG["TAKE_PROFIT_PCT"]


def _append_csv(path, header, row):
    exists = Path(path).exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(header)
        w.writerow(row)


def log_trade(symbol, side, qty, price, reason=""):
    _append_csv(
        CONFIG["TRADE_LOG_FILE"],
        ["ts_utc", "kind", "symbol", "side", "qty", "price", "notional", "reason"],
        [dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
         "FILL", symbol, side, f"{qty:.6f}", f"{price:.4f}",
         f"{qty * price:.4f}", reason],
    )


def log_position_closed(symbol, side, qty, entry, exit, pnl_usd, reason=""):
    _bump_daily_pnl(pnl_usd)
    _append_csv(
        CONFIG["TRADE_LOG_FILE"],
        ["ts_utc", "kind", "symbol", "side", "qty", "price", "notional", "reason"],
        [dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
         "CLOSE", symbol, side, f"{qty:.6f}", f"{exit:.4f}",
         f"{pnl_usd:+.4f}", f"{reason} entry={entry:.4f}"],
    )


# ---- self-test -------------------------------------------------------------

if __name__ == "__main__":
    print("Guardrails module loaded successfully")
    print(json.dumps(CONFIG, indent=2, default=str))
    print(f"NY now: {_ny_now():%Y-%m-%d %H:%M} ET")
    print(f"within trading hours: {_within_trading_hours()}")
    print(f"kill switch active:   {_kill_switch_active()}")
