import { describe, expect, it } from 'vitest'
import {
  formatCadence,
  formatDistance,
  formatDuration,
  formatElevation,
  formatHeartRate,
  formatLocalTime,
  formatPaceOrSpeed,
  sportLabel,
} from '../src/utils/formatters'

describe('distance', () => {
  it('switches from metres to kilometres at 1 km', () => {
    expect(formatDistance(850)).toBe('850 m')
    expect(formatDistance(1000)).toBe('1.0 km')
    expect(formatDistance(12_345)).toBe('12.3 km')
  })

  it('shows a dash rather than inventing a zero', () => {
    expect(formatDistance(null)).toBe('—')
  })
})

describe('duration', () => {
  it('drops hours when there are none', () => {
    expect(formatDuration(125)).toBe('2m 05s')
    expect(formatDuration(3_600)).toBe('1h 00m')
    expect(formatDuration(5_415)).toBe('1h 30m')
  })

  it('treats zero as absent, because a stored zero means untimed', () => {
    expect(formatDuration(0)).toBe('—')
    expect(formatDuration(null)).toBe('—')
  })
})

describe('pace and speed', () => {
  it('gives runners minutes per kilometre', () => {
    expect(formatPaceOrSpeed('running', 10_000, 3_000)).toBe('5:00 /km')
  })

  it('gives cyclists kilometres per hour', () => {
    expect(formatPaceOrSpeed('cycling', 30_000, 3_600)).toBe('30.0 km/h')
  })

  it('carries seconds instead of printing a 60', () => {
    // 4:59.7 per km must not round to "4:60 /km".
    const pace = formatPaceOrSpeed('running', 1_000, 299.7)
    expect(pace).toBe('5:00 /km')
  })

  it('has nothing to say without both numbers', () => {
    expect(formatPaceOrSpeed('running', 0, 100)).toBe('—')
    expect(formatPaceOrSpeed('running', 100, 0)).toBe('—')
  })
})

describe('local time', () => {
  it('uses the offset the file stated', () => {
    // 22:30 UTC at +02:00 is half past midnight, the next day, locally.
    expect(formatLocalTime('2026-05-03T22:30:00Z', 120)).toBe('00:30')
  })

  it('uses one format whether the offset is known or not', () => {
    // Mixing "06:45 PM" and "08:45" in one column reads as two kinds of number.
    expect(formatLocalTime('2026-05-03T22:30:00Z', 120)).toMatch(/^\d{2}:\d{2}$/)
    expect(formatLocalTime('2026-05-03T22:30:00Z', null)).toMatch(/^\d{2}:\d{2}$/)
  })
})

describe('small helpers', () => {
  it('labels sports and defaults politely', () => {
    expect(sportLabel('cycling')).toBe('Cycling')
    expect(sportLabel(null)).toBe('Other')
  })

  it('rounds heart rate and cadence', () => {
    expect(formatHeartRate(142.6)).toBe('143 bpm')
    expect(formatCadence(null)).toBe('—')
    expect(formatElevation(416.7)).toBe('417 m')
  })
})
