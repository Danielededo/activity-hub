import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import RouteMap from '../src/components/RouteMap'

function pointsOf() {
  return screen
    .getByRole('img', { name: /route shape/i })
    .querySelector('polyline')
    .getAttribute('points')
    .split(' ')
    .map((pair) => pair.split(',').map(Number))
}

const at = (latitude, longitude) => ({ latitude, longitude })

describe('RouteMap', () => {
  it('puts north at the top', () => {
    // Going north must move up the screen, and SVG y grows downwards.
    render(<RouteMap samples={[at(45.0, 7.0), at(45.01, 7.0)]} />)
    const [[, firstY], [, secondY]] = pointsOf()

    expect(secondY).toBeLessThan(firstY)
  })

  it('does not stretch a route to fill the box', () => {
    // A track twice as wide as it is tall should stay twice as wide: at this
    // latitude a degree of longitude is much shorter than one of latitude, so
    // an unscaled projection would distort it.
    render(<RouteMap samples={[at(45.0, 7.0), at(45.0, 7.02), at(45.005, 7.02), at(45.0, 7.0)]} />)
    const points = pointsOf()
    const xs = points.map(([x]) => x)
    const ys = points.map(([, y]) => y)
    const width = Math.max(...xs) - Math.min(...xs)
    const height = Math.max(...ys) - Math.min(...ys)

    expect(width).toBeGreaterThan(height)
    expect(width).toBeLessThanOrEqual(100.01)
    expect(height).toBeLessThanOrEqual(100.01)
  })

  it('says so when there is no position data', () => {
    render(<RouteMap samples={[{ latitude: null, longitude: null }]} />)

    expect(screen.getByText(/no position data/i)).toBeInTheDocument()
  })

  it('needs two points to draw a line', () => {
    render(<RouteMap samples={[at(45.0, 7.0)]} />)

    expect(screen.getByText(/no position data/i)).toBeInTheDocument()
  })
})
