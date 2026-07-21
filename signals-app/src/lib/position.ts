/**
 * Position sizing derived from the user's stated capital.
 *
 * Educational illustration only — a fixed-fractional model risking a small
 * percentage of capital to the stop. Not personalised advice.
 */
import type { PositionSize, Signal } from './types';

/** Default fraction of capital risked to the stop per setup (educational). */
export const DEFAULT_RISK_PCT = 0.02; // 2%

/**
 * Compute an illustrative position size for a signal given capital.
 * Uses the midpoint of the entry range as the reference entry.
 */
export function computePositionSize(
  signal: Signal,
  capitalUsd: number,
  riskPct: number = DEFAULT_RISK_PCT,
): PositionSize {
  const entry = (signal.entryLow + signal.entryHigh) / 2;
  const perShareRisk = Math.abs(entry - signal.stopLoss);
  const riskBudget = capitalUsd * riskPct;

  if (perShareRisk <= 0 || capitalUsd <= 0) {
    return { shares: 0, dollarAmount: 0, riskAmount: 0, riskPct };
  }

  // Cap the position at 100% of capital regardless of risk budget.
  const riskSizedShares = Math.floor(riskBudget / perShareRisk);
  const capitalCappedShares = Math.floor(capitalUsd / entry);
  const shares = Math.max(0, Math.min(riskSizedShares, capitalCappedShares));

  return {
    shares,
    dollarAmount: shares * entry,
    riskAmount: shares * perShareRisk,
    riskPct,
  };
}
