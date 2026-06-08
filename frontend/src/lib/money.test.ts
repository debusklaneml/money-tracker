import { describe, it, expect } from 'vitest'
import {
  MILLIUNITS_PER_UNIT,
  toDisplay,
  fromDisplay,
  formatMoney,
  parseMoneyInput,
  toInputString,
} from './money'

describe('MILLIUNITS_PER_UNIT', () => {
  it('is 1000', () => {
    expect(MILLIUNITS_PER_UNIT).toBe(1000)
  })
})

describe('toDisplay', () => {
  it('converts milliunits to currency units', () => {
    expect(toDisplay(1000)).toBe(1)
    expect(toDisplay(-2500)).toBe(-2.5)
    expect(toDisplay(0)).toBe(0)
    expect(toDisplay(1)).toBe(0.001)
  })
})

describe('fromDisplay', () => {
  it('converts currency units to milliunits', () => {
    expect(fromDisplay(1)).toBe(1000)
    expect(fromDisplay(1.5)).toBe(1500)
    expect(fromDisplay(-2.5)).toBe(-2500)
    expect(fromDisplay(0)).toBe(0)
  })

  it('rounds to nearest milliunit, half away from zero', () => {
    expect(fromDisplay(1.2345)).toBe(1235)
    expect(fromDisplay(-1.2345)).toBe(-1235)
    expect(fromDisplay(1.2344)).toBe(1234)
    expect(fromDisplay(-1.2344)).toBe(-1234)
  })
})

describe('toDisplay/fromDisplay round-trips', () => {
  it('round-trips positive, negative, and zero values', () => {
    for (const m of [0, 1000, -1000, 1500, -1500, 1234560, -2500]) {
      expect(fromDisplay(toDisplay(m))).toBe(m)
    }
  })
})

describe('formatMoney', () => {
  it('formats positive values', () => {
    expect(formatMoney(1000)).toBe('$1.00')
    expect(formatMoney(1234560)).toBe('$1,234.56')
  })

  it('formats negative values', () => {
    expect(formatMoney(-1234560)).toBe('-$1,234.56')
  })

  it('formats zero', () => {
    expect(formatMoney(0)).toBe('$0.00')
  })

  it('formats large values', () => {
    expect(formatMoney(1234567890)).toBe('$1,234,567.89')
  })

  it('supports showPlus for positive non-zero values', () => {
    expect(formatMoney(1234560, { showPlus: true })).toBe('+$1,234.56')
    expect(formatMoney(0, { showPlus: true })).toBe('$0.00')
    expect(formatMoney(-1234560, { showPlus: true })).toBe('-$1,234.56')
  })
})

describe('parseMoneyInput', () => {
  it('parses currency-formatted strings', () => {
    expect(parseMoneyInput('$1,234.56')).toBe(1234560)
    expect(parseMoneyInput('1234.56')).toBe(1234560)
  })

  it('parses negatives', () => {
    expect(parseMoneyInput('-12')).toBe(-12000)
  })

  it('parses accounting-style parentheses as negative', () => {
    expect(parseMoneyInput('(12.50)')).toBe(-12500)
    expect(parseMoneyInput('($1,234.56)')).toBe(-1234560)
  })

  it('returns null for empty input', () => {
    expect(parseMoneyInput('')).toBeNull()
    expect(parseMoneyInput('   ')).toBeNull()
  })

  it('returns null for unparseable input', () => {
    expect(parseMoneyInput('abc')).toBeNull()
    expect(parseMoneyInput('.')).toBeNull()
    expect(parseMoneyInput('1.2.3')).toBeNull()
  })

  it('round-trips through fromDisplay rounding', () => {
    expect(parseMoneyInput('1.2345')).toBe(1235)
  })
})

describe('toInputString', () => {
  it('renders a plain two-decimal numeric string with no currency symbol', () => {
    expect(toInputString(100000)).toBe('100.00')
    expect(toInputString(12350)).toBe('12.35')
    expect(toInputString(0)).toBe('0.00')
    expect(toInputString(-2500)).toBe('-2.50')
  })

  it('round-trips exactly through parseMoneyInput for cent-aligned values', () => {
    // The value a user sees when they click to edit must commit back unchanged.
    for (const mu of [100000, 12350, 0, 999990, -2500]) {
      expect(parseMoneyInput(toInputString(mu))).toBe(mu)
    }
  })
})

describe('formatMoney withCents option', () => {
  it('omits decimals and rounds to whole dollars when withCents is false', () => {
    expect(formatMoney(123456, { withCents: false })).toBe('$123')
    expect(formatMoney(123900, { withCents: false })).toBe('$124') // rounds
    expect(formatMoney(-2500, { withCents: false })).toBe('-$3') // rounds away
  })

  it('shows two decimals by default and when withCents is true', () => {
    // 1_234_560 milliunits == $1,234.56.
    expect(formatMoney(1_234_560)).toBe('$1,234.56')
    expect(formatMoney(1_234_560, { withCents: true })).toBe('$1,234.56')
  })
})
