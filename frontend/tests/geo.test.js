import { describe, expect, it } from 'vitest'
import { haversineDistance } from '../src/utils/geo'

describe('haversineDistance', () => {
  it('measures a degree of latitude the same way the backend does', () => {
    // The backend's own constant gives 111,194.9 m for one degree; a frontend
    // that disagreed would show segment speeds inconsistent with the totals.
    expect(haversineDistance(0, 0, 1, 0)).toBeCloseTo(111_194.9, 0)
  })

  it('is zero for a point that has not moved', () => {
    expect(haversineDistance(45.07, 7.68, 45.07, 7.68)).toBe(0)
  })

  it('shortens a degree of longitude away from the equator', () => {
    const equator = haversineDistance(0, 0, 0, 1)
    const turin = haversineDistance(45, 7, 45, 8)

    expect(turin).toBeLessThan(equator)
    expect(turin / equator).toBeCloseTo(Math.cos((45 * Math.PI) / 180), 3)
  })
})
