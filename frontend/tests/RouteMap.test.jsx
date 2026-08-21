import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import RouteMap from '../src/components/RouteMap'
import { CHART_INK, SINGLE_SERIES, ORDINAL_RAMP } from '../src/theme'

const EPOCH = Date.UTC(2026, 5, 22, 6, 30)

function svg() {
  return screen.getByRole('img', { name: /route shape/i })
}

function polylines() {
  return [...svg().querySelectorAll('polyline')]
}

function pointsOf() {
  return polylines()[0]
    .getAttribute('points')
    .split(' ')
    .map((pair) => pair.split(',').map(Number))
}

function strokes() {
  return polylines().map((line) => line.getAttribute('stroke'))
}

const at = (latitude, longitude) => ({ latitude, longitude })

/**
 * A track heading east, built from [degrees, seconds] hops.
 *
 * A hop of 0.001 degrees at this latitude is about 79 m, so the seconds decide
 * the speed: 3 s is a 94 km/h descent and 10 s a 28 km/h cruise. Anything
 * quicker than 3 s per hop crosses the component's implausible-speed ceiling
 * and is treated as a lost signal, which is easy to do by accident.
 */
function eastward(hops, startAt = EPOCH) {
  const samples = [{ latitude: 45, longitude: 7, timestamp: new Date(startAt).toISOString() }]
  let longitude = 7
  let moment = startAt
  for (const [degrees, seconds] of hops) {
    longitude += degrees
    moment += seconds * 1000
    samples.push({ latitude: 45, longitude, timestamp: new Date(moment).toISOString() })
  }
  return samples
}

/** Hops that vary in pace, slowest first, all of them plausible. */
const VARIED = [10, 9, 8, 7, 6, 5, 4, 3].map((seconds) => [0.001, seconds])

/** The same, with a stretch where the receiver clearly lost the plot. */
const WITH_A_GAP = [...VARIED.slice(0, 4), [0.5, 3], [-0.5, 3], ...VARIED.slice(4)]

/** Pin an element's box, so the letterbox maths has something real to work on. */
function stubBox(element, { width, height, left = 0, top = 0 }) {
  element.getBoundingClientRect = () => ({
    width,
    height,
    left,
    top,
    right: left + width,
    bottom: top + height,
    x: left,
    y: top,
  })
}

describe('RouteMap geometry', () => {
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
    const points = polylines().flatMap((line) =>
      line
        .getAttribute('points')
        .split(' ')
        .map((pair) => pair.split(',').map(Number)),
    )
    const xs = points.map(([x]) => x)
    const ys = points.map(([, y]) => y)

    expect(Math.max(...xs) - Math.min(...xs)).toBeGreaterThan(Math.max(...ys) - Math.min(...ys))
    expect(Math.max(...xs) - Math.min(...xs)).toBeLessThanOrEqual(100.01)
    expect(Math.max(...ys) - Math.min(...ys)).toBeLessThanOrEqual(100.01)
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

describe('RouteMap speed colouring', () => {
  it('colours the track by how fast each stretch was', () => {
    // Ten hops from slow to fast: the bands should span the whole ramp.
    render(<RouteMap samples={eastward(VARIED)} sportType="cycling" />)
    const used = new Set(strokes())

    expect(used.size).toBeGreaterThan(1)
    expect([...used].every((stroke) => ORDINAL_RAMP.light.includes(stroke))).toBe(true)
  })

  it('never paints the track a colour outside the documented set', () => {
    // Either a validated step of the ramp, or the grey that means "not
    // measured". Anything else would be a hue chosen by eye.
    const allowed = [...ORDINAL_RAMP.light, CHART_INK.light.axis]
    render(<RouteMap samples={eastward(WITH_A_GAP)} sportType="running" />)

    for (const stroke of strokes()) {
      expect(allowed).toContain(stroke)
    }
  })

  it('draws one plain line when nothing distinguishes the speeds', () => {
    // Five bands would be five names for the same number.
    render(<RouteMap samples={eastward(Array(8).fill([0.001, 5]))} sportType="cycling" />)

    expect(polylines()).toHaveLength(1)
    expect(strokes()[0]).toBe(SINGLE_SERIES.light)
  })

  it('draws one plain line when the file carried no timestamps', () => {
    // The distance is known and the time is not, so there is no speed to show.
    render(<RouteMap samples={[at(45, 7), at(45, 7.001), at(45, 7.002)]} sportType="cycling" />)

    expect(polylines()).toHaveLength(1)
    expect(screen.queryByRole('figure')?.querySelector('figcaption')).toBeNull()
  })

  it('greys a lost signal rather than calling it a speed', () => {
    // One hop jumps half a degree in seconds — some 39 km. It cannot take the
    // top band, and it cannot take the middle one either: the single-series
    // blue IS the ramp's middle step, so painting an unmeasured stretch with it
    // would read as average pace instead of "no idea".
    render(<RouteMap samples={eastward(WITH_A_GAP)} sportType="cycling" />)

    expect(strokes()).toContain(CHART_INK.light.axis)
    expect(ORDINAL_RAMP.light).not.toContain(CHART_INK.light.axis)
  })

  it('explains the grey in the legend', () => {
    render(<RouteMap samples={eastward(WITH_A_GAP)} sportType="cycling" />)

    expect(screen.getByRole('figure').textContent).toMatch(/no signal/i)
  })

  it('does not mention a signal gap when there is none', () => {
    render(<RouteMap samples={eastward(VARIED)} sportType="cycling" />)

    expect(screen.getByRole('figure').textContent).not.toMatch(/no signal/i)
  })

  it('handles a track that alternates between two speeds', () => {
    // Interval training is exactly this shape, and it is the case where runs
    // are shortest and most numerous — two points each, back to back. It is
    // also where a key built from a run's first point could repeat.
    const intervals = [10, 4, 10, 4, 10, 4, 10, 4].map((seconds) => [0.001, seconds])
    render(<RouteMap samples={eastward(intervals)} sportType="running" />)

    expect(polylines().length).toBeGreaterThan(4)
    for (const stroke of strokes()) {
      expect(ORDINAL_RAMP.light).toContain(stroke)
    }
  })
})

describe('RouteMap markers', () => {
  it('marks the start and the finish', () => {
    render(<RouteMap samples={eastward(Array(3).fill([0.001, 5]))} sportType="cycling" />)

    expect(svg().querySelector('circle title').textContent).toBe('Start')
    expect(svg().querySelector('rect title').textContent).toBe('Finish')
  })

  it('tells them apart by shape, not by colour', () => {
    // Green against red is the obvious choice and fails for a red-green reader:
    // 4.1 ΔE under simulated deuteranopia, where the target is 8. Same ink,
    // different shape, is safe by construction.
    render(<RouteMap samples={eastward(Array(3).fill([0.001, 5]))} sportType="cycling" />)
    const start = svg().querySelector('circle')
    const finish = svg().querySelector('rect')

    expect(start.getAttribute('fill')).toBe(finish.getAttribute('fill'))
    expect(start.tagName).not.toBe(finish.tagName)
  })

  it('rings each marker in the surface colour so it survives a crossing track', () => {
    render(<RouteMap samples={eastward(Array(3).fill([0.001, 5]))} sportType="cycling" />)
    const start = svg().querySelector('circle')

    expect(start.getAttribute('stroke')).toBe('#ffffff')
    expect(start.getAttribute('stroke-width')).toBe('2')
  })
})

describe('RouteMap legend', () => {
  it('labels the ends of the ramp in the unit the sport reads', () => {
    render(<RouteMap samples={eastward(VARIED)} sportType="cycling" />)

    expect(screen.getByRole('figure').textContent).toMatch(/km\/h/)
  })

  it('gives a runner pace rather than speed', () => {
    render(<RouteMap samples={eastward(VARIED)} sportType="running" />)

    expect(screen.getByRole('figure').textContent).toMatch(/\/km/)
  })

  it('names the ends of the ramp with the slowest and fastest stretch', () => {
    // Not the outer cut points: labelling a ramp with its 20th and 80th
    // percentile understates the range, and on a steady ride prints the same
    // figure at both ends, which reads as a contradiction.
    render(<RouteMap samples={eastward(VARIED)} sportType="cycling" />)
    const shown = [...screen.getByRole('figure').querySelectorAll('figcaption > span')]
      .map((span) => span.textContent)
      .filter((text) => /km\/h/.test(text))

    expect(shown).toHaveLength(2)
    expect(shown[0]).not.toBe(shown[1])
  })

  it('drops the encoding when both ends would read the same', () => {
    // A ride held to within a rounding error of one speed. The quantiles do
    // not collapse — the hop times genuinely differ — but every one of them
    // prints as 56.6 km/h, so five shades would be five names for one number.
    // The labels are the thing that rules it out, not the arithmetic.
    const barely = [5, 5.001, 5.003, 5.004, 5, 5.002, 5.001, 5.003].map((s) => [0.001, s])
    render(<RouteMap samples={eastward(barely)} sportType="cycling" />)

    expect(polylines()).toHaveLength(1)
    expect(strokes()[0]).toBe(SINGLE_SERIES.light)
    expect(screen.getByRole('figure').querySelector('figcaption')).toBeNull()
  })

  it('shows no legend when there is no encoding to explain', () => {
    render(<RouteMap samples={eastward(Array(8).fill([0.001, 5]))} sportType="cycling" />)

    expect(screen.getByRole('figure').querySelector('figcaption')).toBeNull()
  })
})

describe('RouteMap hover', () => {
  function hover(clientX, clientY, box = { width: 400, height: 200 }) {
    const element = svg()
    stubBox(element, box)
    fireEvent.pointerMove(element, { clientX, clientY })
    return element
  }

  it('reports distance, time and speed where the pointer is', () => {
    render(<RouteMap samples={eastward(VARIED)} sportType="cycling" />)

    hover(200, 100)

    const tip = screen.getByRole('tooltip')
    expect(tip.textContent).toMatch(/in/)
    expect(tip.textContent).toMatch(/km\/h/)
  })

  it('accounts for the letterboxing rather than scaling the pointer flat', () => {
    // The SVG keeps its aspect ratio inside a 400x200 box, so the drawing is a
    // 200-wide square with 100px of padding each side. At clientX 300 the
    // pointer is at the right-hand edge of the drawing — the last sample.
    // Treating x as a plain proportion of the element would land at 77% of the
    // way along instead, several samples short.
    render(<RouteMap samples={eastward(Array(5).fill([0.001, 5]))} sportType="cycling" />)

    hover(300, 100)

    const ring = svg().querySelector('circle[fill="none"]')
    expect(Number(ring.getAttribute('cx'))).toBeCloseTo(100, 0)
  })

  it('picks the first sample at the other edge', () => {
    render(<RouteMap samples={eastward(Array(5).fill([0.001, 5]))} sportType="cycling" />)

    hover(100, 100)

    const ring = svg().querySelector('circle[fill="none"]')
    expect(Number(ring.getAttribute('cx'))).toBeCloseTo(0, 0)
  })

  it('reads the start as a zero, not as a missing figure', () => {
    // formatDuration answers "—" for zero; on a tooltip that reads as data the
    // file did not have, when in fact no time has passed there yet.
    render(<RouteMap samples={eastward(VARIED)} sportType="cycling" />)

    hover(100, 100)

    expect(screen.getByRole('tooltip').textContent).toMatch(/0s/)
  })

  it('says nothing about time for a track that has none', () => {
    render(<RouteMap samples={[at(45, 7), at(45, 7.001), at(45, 7.002)]} sportType="cycling" />)

    hover(200, 100)

    const tip = screen.getByRole('tooltip')
    expect(tip.textContent).toMatch(/in/)
    expect(tip.textContent).not.toMatch(/0s/)
  })

  it('clears when the pointer leaves', () => {
    render(<RouteMap samples={eastward(VARIED)} sportType="cycling" />)
    hover(200, 100)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()

    fireEvent.pointerLeave(svg())

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('does nothing when the element has not been laid out yet', () => {
    // jsdom and a first paint both report a zero box; dividing by it would put
    // the pointer at infinity.
    render(<RouteMap samples={eastward(Array(3).fill([0.001, 5]))} sportType="cycling" />)

    fireEvent.pointerMove(svg(), { clientX: 10, clientY: 10 })

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})
