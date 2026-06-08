/**
 * money.ts — single source of truth for monetary value conversion & display.
 *
 * MILLIUNIT CONVENTION (mirrors the backend):
 * All monetary amounts on the wire are stored as INTEGERS in "milliunits",
 * where 1 currency unit (e.g. $1.00) == 1000 milliunits. So $1.00 -> 1000,
 * $0.001 -> 1, $-2.50 -> -2500.
 *
 * Inflows are positive, outflows are negative. We never store the value as a
 * float — milliunits keep money exact in integer space and avoid binary
 * floating-point rounding drift. This module is the ONLY place that converts
 * between milliunits and human-facing display, and that parses user-typed
 * money back into milliunits (used later by the editable "Assigned" cells).
 */

/** Number of milliunits in one whole currency unit. */
export const MILLIUNITS_PER_UNIT = 1000

/**
 * Convert milliunits (integer) to currency units as a JS number.
 * e.g. 1000 -> 1, -2500 -> -2.5, 0 -> 0.
 *
 * The result is a float and is intended for display/formatting only —
 * never round-trip arithmetic through it for stored values.
 */
export function toDisplay(milliunits: number): number {
  return milliunits / MILLIUNITS_PER_UNIT
}

/**
 * Convert currency units to milliunits (integer), rounding to the nearest
 * milliunit with ties rounded half away from zero.
 * e.g. 1.5 -> 1500, 1.2345 -> 1235, -1.2345 -> -1235.
 */
export function fromDisplay(units: number): number {
  const scaled = units * MILLIUNITS_PER_UNIT
  // Math.round rounds half toward +Infinity, which is asymmetric for
  // negatives. Round the magnitude and reapply the sign to get
  // consistent "half away from zero" behavior.
  const sign = scaled < 0 ? -1 : 1
  return sign * Math.round(Math.abs(scaled))
}

/** Base formatter: USD currency, always two fraction digits. */
const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
})

/**
 * Format milliunits as a localized currency string.
 *
 * - opts.withCents (default true): show two decimal places ("$1,234.56").
 *   Kept simple — the default formatter always shows 2 decimals.
 * - opts.showPlus (default false): prefix positive, non-zero values with "+".
 *
 * Negatives render as "-$1,234.56". Zero renders "$0.00".
 */
export function formatMoney(
  milliunits: number,
  opts?: { withCents?: boolean; showPlus?: boolean },
): string {
  const showPlus = opts?.showPlus ?? false

  const units = toDisplay(milliunits)
  // Intl already renders the "-" sign for negative values.
  const formatted = currencyFormatter.format(units)

  if (showPlus && milliunits > 0) {
    return `+${formatted}`
  }
  return formatted
}

/**
 * Parse free-form user money input into milliunits.
 *
 * Accepts forms like "$1,234.56", "1234.56", "-12", "(12.50)" (accounting
 * negative). Strips "$", ",", and surrounding whitespace. Wrapping
 * parentheses are treated as a negative value.
 *
 * Returns null for empty or unparseable input.
 */
export function parseMoneyInput(text: string): number | null {
  if (text == null) return null

  let s = text.trim()
  if (s === '') return null

  // Accounting-style negative: wrapping parentheses.
  let negative = false
  if (s.startsWith('(') && s.endsWith(')')) {
    negative = true
    s = s.slice(1, -1).trim()
  }

  // Strip currency symbol, thousands separators, and any internal whitespace.
  s = s.replace(/[$,\s]/g, '')
  if (s === '') return null

  // Leading sign handling (after parentheses already accounted for).
  if (s.startsWith('+')) {
    s = s.slice(1)
  } else if (s.startsWith('-')) {
    negative = !negative
    s = s.slice(1)
  }
  if (s === '') return null

  // At this point only digits and an optional single decimal point are valid.
  if (!/^\d*\.?\d*$/.test(s) || s === '.') return null

  const value = Number(s)
  if (!Number.isFinite(value)) return null

  const milliunits = fromDisplay(value)
  return negative ? -milliunits : milliunits
}
