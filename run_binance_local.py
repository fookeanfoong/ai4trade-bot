#!/usr/bin/env python3
"""
Local runner for the Binance SPOT crypto book — "PC on = it trades".

This is the piece that makes the bot run ON YOUR COMPUTER instead of on GitHub's
cloud. While this window is open it loops forever: every INTERVAL minutes it
refreshes ETH/BTC technicals, regenerates long-only setups, and runs one
live_trader.py cycle against Binance. Close the window (or Ctrl+C) and it stops —
no cloud, no schedule, nothing trades while your PC is off.

    python run_binance_local.py              # loop on Binance TESTNET (fake money)
    python run_binance_local.py --once       # run a single cycle and exit
    python run_binance_local.py --dry-run    # full logic, place NO orders
    python run_binance_local.py --interval 5 # loop every 5 minutes instead of 15

Keys come from the environment (BINANCE_API_KEY / BINANCE_API_SECRET). On Windows
launch it via run_binance.bat, which loads them from binance_keys.bat first.

⚠️  OPEN POSITIONS ARE ONLY PROTECTED WHILE THIS RUNS. The stop-loss is managed in
software here, not resting on Binance. Before you shut the PC down, make sure the
book is FLAT (this runner prints open positions every cycle and on exit). A
"flatten everything now" pass:  python run_binance_local.py --flatten --once
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# --- the tuned crypto config, Binance edition --------------------------------
# Mirrors .github/workflows/trade_crypto.yml (the config the backtest picked),
# with the Binance-specific bits changed: BROKER, testnet flag, cheaper fees
# (spot taker 0.10%/side vs Alpaca 0.25%), a separate state file/report dir, and
# a universe narrowed to ETH (+BTC as the market-regime reference).
BOOK_ENV = {
    "BROKER": "binance",
    "BINANCE_PAPER": os.environ.get("BINANCE_PAPER", "true"),   # testnet by default
    "MARKET_24_7": "yes",
    "CRYPTO_SYMBOLS": os.environ.get("CRYPTO_SYMBOLS", "BTC,ETH"),
    "REGIME_SYMBOLS": "BTC",
    "CRYPTO_INTERVAL": os.environ.get("CRYPTO_INTERVAL", "1h"),
    "CRYPTO_RANGE": os.environ.get("CRYPTO_RANGE", "1mo"),
    "DISABLE_SIGNAL_EXIT": "yes",
    "SIGNALS_FILE": "signals_crypto.json",
    "QUOTES_FILE": "quotes_crypto.json",
    "STATE_FILE": "live_trader_binance_state.json",
    "REPORTS_SUBDIR": "live_trader_binance",
    "BOOK_EQUITY": os.environ.get("BOOK_EQUITY", "200"),
    "RISK_PCT": "0.08",
    "BASE_SLICES": "1",
    "LEVERAGE_CAP": "1.0",             # spot is cash-only, no leverage
    "ALLOW_FRACTIONAL": "yes",
    "MAX_POSITIONS": "1",             # demo: one name (ETH) at a time
    "ENABLE_SHORT": "no",             # spot cannot short
    "NET_PROFIT_MODE": "yes",
    "FEE_RATE": os.environ.get("FEE_RATE", "0.0010"),   # Binance spot taker/side
    "NET_TARGET_MIN_USD": "0.50",
    "NET_TARGET_MAX_USD": "1.00",
    "RUN_WINNERS": "yes",
    "TRAIL_GIVEBACK_PCT": "0.006",
    "VOL_SPAN_LO": "0.015",
    "VOL_SPAN_HI": "0.050",
    "MIN_RR_NET": "1.0",
    "MIN_HOLD_MIN": "20",
    "MAX_TARGET_MOVE_PCT": "0.035",
}
# Entry gates that must be set on the SIGNAL step (a different process).
SIGNAL_ENV = {"ALLOW_FLAT_TREND": "yes", "CRYPTO_SYMBOLS": BOOK_ENV["CRYPTO_SYMBOLS"],
              "CRYPTO_INTERVAL": BOOK_ENV["CRYPTO_INTERVAL"],
              "CRYPTO_RANGE": BOOK_ENV["CRYPTO_RANGE"]}


def _run(script: str, extra_env: dict, *args: str, quiet_ok: bool = False) -> int:
    env = dict(os.environ)
    env.update(extra_env)
    try:
        r = subprocess.run([PY, os.path.join(ROOT, script), *args],
                           env=env, cwd=ROOT)
        return r.returncode
    except Exception as e:
        if not quiet_ok:
            print(f"  ! {script} failed to launch: {e}")
        return 1


def ensure_baseline() -> None:
    """On a fresh account the runner snapshots current balances so preloaded
    testnet coins (and any coin you already hold) are never treated as bot
    positions. Skips if the snapshot already exists, or on --dry-run."""
    baseline = os.path.join(ROOT, os.environ.get("BINANCE_BASELINE_FILE",
                                                 "binance_baseline.json"))
    if os.path.exists(baseline):
        return
    if not (os.environ.get("BINANCE_API_KEY") and os.environ.get("BINANCE_API_SECRET")):
        return  # no keys yet; connect() will explain
    print("First run: snapshotting current Binance balances as the 'flat' "
          "baseline (preloaded/your coins won't be traded)...")
    env = dict(os.environ)
    env.update({"BINANCE_PAPER": BOOK_ENV["BINANCE_PAPER"]})
    subprocess.run([PY, os.path.join(ROOT, "broker_binance.py"),
                    "--snapshot-baseline"], env=env, cwd=ROOT)


def _mode_label(dry: bool) -> str:
    if dry:
        return "DRY-RUN"
    return "TESTNET" if BOOK_ENV["BINANCE_PAPER"].lower() != "false" else "LIVE"


def one_cycle(dry: bool, flatten: bool) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n=== cycle @ {stamp} ({_mode_label(dry)}) ===")
    # 1) real-market technicals for ETH (+BTC regime)
    _run("quotes_crypto.py", SIGNAL_ENV, quiet_ok=True)
    # 2) crash-news sentinel (free, best-effort)
    _run("news_crypto.py", SIGNAL_ENV, quiet_ok=True)
    # 3) long-only setups
    _run("generate_signals_crypto.py", SIGNAL_ENV, quiet_ok=True)
    # 4) execute against Binance
    trade_env = dict(BOOK_ENV)
    if flatten:
        trade_env["FLATTEN_ALL"] = "yes"
    args = ("--dry-run",) if dry else ()
    _run("live_trader.py", trade_env, *args)


def main() -> int:
    ap = argparse.ArgumentParser(description="Local Binance spot runner (PC on = trades)")
    ap.add_argument("--once", action="store_true", help="one cycle then exit")
    ap.add_argument("--dry-run", action="store_true", help="run logic, place NO orders")
    ap.add_argument("--flatten", action="store_true", help="close every open position this cycle")
    ap.add_argument("--interval", type=float,
                    default=float(os.environ.get("BINANCE_INTERVAL_MIN", "15")),
                    help="minutes between cycles (default 15)")
    args = ap.parse_args()

    env = "DRY-RUN" if args.dry_run else (
        "TESTNET (fake money)" if BOOK_ENV["BINANCE_PAPER"].lower() != "false" else "LIVE (REAL money)")
    print("Binance local runner — PC on = it trades, close this window = it stops.")
    print(f"  mode      : {env}")
    print(f"  universe  : {BOOK_ENV['CRYPTO_SYMBOLS']} (trading ETH; BTC = regime ref)")
    print(f"  book      : ${BOOK_ENV['BOOK_EQUITY']} | interval {args.interval:g} min | {BOOK_ENV['CRYPTO_INTERVAL']} bars")
    if not args.dry_run and not (os.environ.get("BINANCE_API_KEY") and os.environ.get("BINANCE_API_SECRET")):
        print("\n  ⚠  BINANCE_API_KEY / BINANCE_API_SECRET are not set. Set them "
              "(run_binance.bat / binance_keys.bat on Windows) or use --dry-run.")
    if not args.dry_run:
        ensure_baseline()

    try:
        if args.once or args.flatten:
            one_cycle(args.dry_run, args.flatten)
        else:
            while True:
                one_cycle(args.dry_run, flatten=False)
                print(f"  ...sleeping {args.interval:g} min (Ctrl+C to stop)")
                time.sleep(max(30.0, args.interval * 60))
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        # Do NOT walk away with an open position — nothing manages the stop once
        # this process is gone.
        print("\nRunner exited. If any position is OPEN, its software stop is no "
              "longer running. Check the last cycle's report in "
              f"reports/{BOOK_ENV['REPORTS_SUBDIR']}/ and flatten if needed:")
        print("    python run_binance_local.py --flatten --once")
    return 0


if __name__ == "__main__":
    sys.exit(main())
