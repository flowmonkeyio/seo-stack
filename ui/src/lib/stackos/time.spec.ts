import { describe, expect, it } from 'vitest'

import {
  formatDurationBetween,
  formatDurationMinutes,
  formatRelativeDateTime,
} from './time'

const NOW = new Date('2026-06-09T12:00:00Z')

describe('formatRelativeDateTime', () => {
  it('handles empty and invalid values', () => {
    expect(formatRelativeDateTime(null, NOW)).toBe('-')
    expect(formatRelativeDateTime(undefined, NOW)).toBe('-')
    expect(formatRelativeDateTime('not-a-date', NOW)).toBe('not-a-date')
  })

  it('formats past timestamps across scales', () => {
    expect(formatRelativeDateTime('2026-06-09T11:59:40Z', NOW)).toBe('just now')
    expect(formatRelativeDateTime('2026-06-09T11:14:00Z', NOW)).toBe('46m ago')
    expect(formatRelativeDateTime('2026-06-09T03:00:00Z', NOW)).toBe('9h ago')
    expect(formatRelativeDateTime('2026-06-03T12:00:00Z', NOW)).toBe('6d ago')
  })

  it('falls back to a date for older timestamps', () => {
    const out = formatRelativeDateTime('2026-01-09T12:00:00Z', NOW)
    expect(out).toMatch(/2026/)
  })

  it('formats future timestamps', () => {
    expect(formatRelativeDateTime('2026-06-09T12:30:00Z', NOW)).toBe('in 30m')
    expect(formatRelativeDateTime('2026-06-10T13:00:00Z', NOW)).toBe('in 1d')
  })
})

describe('formatDurationMinutes', () => {
  it('handles edge values', () => {
    expect(formatDurationMinutes(null)).toBe('-')
    expect(formatDurationMinutes(undefined)).toBe('-')
    expect(formatDurationMinutes(0.4)).toBe('<1m')
  })

  it('formats across scales', () => {
    expect(formatDurationMinutes(14)).toBe('14m')
    expect(formatDurationMinutes(142)).toBe('2h 22m')
    expect(formatDurationMinutes(937)).toBe('15h 37m')
    expect(formatDurationMinutes(1500)).toBe('1d 1h')
    expect(formatDurationMinutes(1440)).toBe('1d')
  })
})

describe('formatDurationBetween', () => {
  it('computes closed and open-ended ranges', () => {
    expect(
      formatDurationBetween('2026-06-09T10:00:00Z', '2026-06-09T11:30:00Z', NOW),
    ).toBe('1h 30m')
    expect(formatDurationBetween('2026-06-09T11:00:00Z', null, NOW)).toBe('1h')
    expect(formatDurationBetween(null, null, NOW)).toBe('-')
  })
})
