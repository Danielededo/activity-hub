import { describe, expect, it } from 'vitest'
import {
  cadenceUnit,
  formatCadence,
  formatDistance,
  formatDuration,
  formatElapsed,
  formatElevation,
  formatHeartRate,
  formatLocalTime,
  formatPaceOrSpeed,
  formatRate,
  formatShortDuration,
  formatSpeed,
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

describe('formatShortDuration', () => {
  it('drops the seconds an axis has no room for', () => {
    // formatDuration gives "55m 00s"; beside a y axis that is wide enough to be
    // clipped, and a clipped label reads as a different number.
    expect(formatShortDuration(3_300)).toBe('55m')
    expect(formatShortDuration(6_600)).toBe('1h 50m')
    expect(formatShortDuration(13_200)).toBe('3h 40m')
  })

  it('writes a bare zero rather than a dash', () => {
    expect(formatShortDuration(0)).toBe('0')
    expect(formatShortDuration(null)).toBe('0')
  })
})

describe('formatRate', () => {
  it('gives a cyclist speed and a runner pace from the same rate', () => {
    // 5 m/s is 18 km/h, and 3:20 per kilometre.
    expect(formatRate('cycling', 5)).toBe('18.0 km/h')
    expect(formatRate('running', 5)).toBe('3:20 /km')
  })

  it('has nothing to say about a rate of nothing', () => {
    expect(formatRate('cycling', 0)).toBe('—')
    expect(formatRate('cycling', null)).toBe('—')
  })
})

describe('formatSpeed', () => {
  it('counts every sport in km/h, because an axis is one scale', () => {
    expect(formatSpeed(5)).toBe('18.0 km/h')
  })

  it('writes a standing start as zero, not as a dash', () => {
    // The zero tick of the comparison axis rendered as an em dash: a rate of
    // nothing has no pace, but it has a speed, and it is where the axis starts.
    expect(formatSpeed(0)).toBe('0.0 km/h')
    expect(formatSpeed(null)).toBe('—')
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

  it('counts cadence in revolutions on a bike and in strides on foot', () => {
    // A run's cadence is written per leg by every exporter this reads, so it
    // is strides per minute, not crank revolutions.
    expect(formatCadence(82.4, 'cycling')).toBe('82 rpm')
    expect(formatCadence(86, 'running')).toBe('86 spm')
    expect(formatCadence(58, 'hiking')).toBe('58 spm')
  })

  it('puts a zero on an axis, not a dash', () => {
    // formatDuration answers "—" for zero, which is right for a duration that
    // was never recorded and wrong for the origin of a trace's x axis.
    expect(formatElapsed(0)).toBe('0s')
    expect(formatElapsed(90)).toBe('1m 30s')
    expect(formatElapsed(null)).toBe('—')
  })

  it('names the cadence unit without a value, for a chart axis', () => {
    expect(cadenceUnit('cycling')).toBe('rpm')
    expect(cadenceUnit('running')).toBe('spm')
    expect(cadenceUnit(undefined)).toBe('rpm')
  })
})
