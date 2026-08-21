import { describe, expect, it } from 'vitest'
import { SPORT_ORDER, palette, sportColor } from '../src/theme'

describe('the sport palette', () => {
  it('keeps a fixed slot order', () => {
    // Colour follows the entity, so this order must not drift: a reorder
    // would repaint every existing chart and break the validated pairings.
    expect(SPORT_ORDER).toEqual(['cycling', 'running', 'hiking', 'other'])
  })

  it('gives every sport in the order its own hue', () => {
    const hues = SPORT_ORDER.map((sport) => sportColor(sport))
    expect(new Set(hues).size).toBe(SPORT_ORDER.length)
  })

  it('falls back to the "other" slot instead of inventing a hue', () => {
    expect(sportColor('kitesurfing')).toBe(palette().other)
    expect(sportColor(undefined)).toBe(palette().other)
  })

  it('has a distinct step for dark mode rather than reusing the light one', () => {
    for (const sport of SPORT_ORDER) {
      expect(sportColor(sport, true)).not.toBe(sportColor(sport, false))
    }
  })
})
