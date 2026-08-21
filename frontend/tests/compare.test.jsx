import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CompareActivities from '../src/components/CompareActivities'
import CompareChart from '../src/components/CompareChart'
import * as api from '../src/api/client'
import { distanceSeries, measureTrack, sharedGrid } from '../src/utils/track'

vi.mock('../src/api/client', async (importOriginal) =>
  (await import('./mockClient')).mockClient(importOriginal),
)

const EPOCH = Date.UTC(2026, 6, 20, 8, 0)

/** Samples heading north, one every `seconds`, `step` degrees apart. */
function track(count, { step = 0.001, seconds = 10, ele = 200 } = {}) {
  return Array.from({ length: count }, (_, index) => ({
    sequence: index,
    latitude: 45 + index * step,
    longitude: 7,
    elevation: ele + index,
    timestamp: new Date(EPOCH + index * seconds * 1000).toISOString(),
  }))
}

const RIDE = {
  id: 1,
  name: 'Tuesday loop',
  sport_type: 'cycling',
  source: 'strava',
  file_format: 'gpx',
  start_time: '2026-07-20T08:00:00Z',
  utc_offset_minutes: null,
  total_distance: 20_000,
  total_time: 3_600,
  total_elevation_gain: 200,
  avg_heart_rate: 140,
  avg_cadence: 84,
}

const OTHER = {
  ...RIDE,
  id: 2,
  name: 'Same loop, faster',
  start_time: '2026-07-27T08:00:00Z',
  total_distance: 20_000,
  total_time: 3_200,
}

const A_RUN = { ...RIDE, id: 3, name: 'A run', sport_type: 'running' }

beforeEach(() => {
  vi.clearAllMocks()
  api.fetchWorkouts.mockResolvedValue({ items: [RIDE, OTHER], total: 2, limit: 50, offset: 0 })
  api.fetchTrackPoints.mockResolvedValue({
    workout_id: 1,
    total: 5,
    returned: 5,
    stride: 1,
    items: track(5),
  })
})

describe('measureTrack and distanceSeries', () => {
  it('accumulates distance and reports the speed of each hop', () => {
    const { distances, speeds } = measureTrack(track(3))

    expect(distances[0]).toBe(0)
    expect(distances[2]).toBeGreaterThan(distances[1])
    expect(speeds).toHaveLength(2)
    expect(speeds[0]).toBeCloseTo(speeds[1], 3)
  })

  it('starts the plotted series at zero distance, not at the second sample', () => {
    // The first sample has no hop behind it; borrowing the one that leaves it
    // keeps the line from starting a hundred metres in.
    const series = distanceSeries(track(4))

    expect(series[0].distance).toBe(0)
    expect(series[0].speed).not.toBeNull()
  })

  it('refuses a speed no human produced', () => {
    // Half a degree in ten seconds is a lost fix, not a sprint.
    const jumpy = track(2)
    jumpy[1].latitude = 45.5
    const series = distanceSeries(jumpy)

    expect(series.every((point) => point.speed === null)).toBe(true)
  })

  it('has nothing to plot for a track with no positions', () => {
    expect(distanceSeries([{ latitude: null, longitude: null }])).toEqual([])
    expect(distanceSeries([])).toEqual([])
  })

  it('holds the clock across a sample with no time', () => {
    const samples = track(3)
    samples[1].timestamp = null
    const { elapsed } = measureTrack(samples)

    expect(elapsed[1]).toBe(elapsed[0])
  })
})

describe('sharedGrid', () => {
  const near = [
    { distance: 0, speed: 4 },
    { distance: 100, speed: 6 },
    { distance: 200, speed: 8 },
  ]
  const far = [
    { distance: 0, speed: 10 },
    { distance: 400, speed: 2 },
  ]

  it('gives every activity a value at every shared distance', () => {
    // The defect this replaced: merging each track's own samples into shared
    // rows left one value and one gap per row, so a chart that does not bridge
    // gaps drew both lines shattered exactly where they overlapped.
    const rows = sharedGrid([{ points: near }, { points: far }], 'speed', 5)
    const overlapping = rows.filter((row) => row.distance <= 200)
    expect(overlapping).toHaveLength(3)
    for (const row of overlapping) {
      expect(row.v0).toBeTypeOf('number')
      expect(row.v1).toBeTypeOf('number')
    }
  })

  it('interpolates straight between the samples either side', () => {
    const rows = sharedGrid([{ points: near }], 'speed', 5)
    // Grid of five over 200 m: 0, 50, 100, 150, 200.
    expect(rows.map((row) => row.distance)).toEqual([0, 50, 100, 150, 200])
    expect(rows.map((row) => row.v0)).toEqual([4, 5, 6, 7, 8])
  })

  it('stops the shorter activity rather than stretching it', () => {
    const rows = sharedGrid([{ points: near }, { points: far }], 'speed', 5)
    expect(rows.at(-1).distance).toBe(400)
    expect(rows.at(-1).v0).toBeUndefined()
    expect(rows.at(-1).v1).toBe(2)
  })

  it('has no grid to build when nothing carries the measure', () => {
    expect(sharedGrid([{ points: near }], 'elevation', 5)).toEqual([])
    expect(sharedGrid([], 'speed', 5)).toEqual([])
  })
})

describe('CompareChart', () => {
  const series = [
    { id: 1, name: 'Mine', points: [{ distance: 0, speed: 5 }, { distance: 500, speed: 6 }] },
    { id: 2, name: 'Theirs', points: [{ distance: 0, speed: 4 }, { distance: 500, speed: 7 }] },
  ]

  it('names both activities, so identity is never colour alone', () => {
    render(<CompareChart title="Pace" series={series} dataKey="speed" formatValue={String} />)

    expect(screen.getByText('Mine')).toBeInTheDocument()
    expect(screen.getByText('Theirs')).toBeInTheDocument()
  })

  it('draws nothing when only one activity has the measure', () => {
    // An elevation chart with one line is the single-activity trace, not a
    // comparison, and drawing it here would say the other had none.
    const lopsided = [series[0], { id: 2, name: 'Theirs', points: [{ distance: 0 }] }]
    const { container } = render(
      <CompareChart title="Pace" series={lopsided} dataKey="speed" formatValue={String} />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})

describe('CompareActivities', () => {
  it('offers the other activities of the same sport', async () => {
    render(<CompareActivities workout={RIDE} userId={1} />)

    expect(await screen.findByRole('option', { name: /Same loop, faster/ })).toBeInTheDocument()
    await waitFor(() =>
      expect(api.fetchWorkouts).toHaveBeenCalledWith(
        expect.objectContaining({ sportType: 'cycling' }),
      ),
    )
  })

  it('never offers the activity against itself', async () => {
    render(<CompareActivities workout={RIDE} userId={1} />)
    await screen.findByRole('option', { name: /Same loop, faster/ })

    expect(screen.queryByRole('option', { name: /Tuesday loop/ })).not.toBeInTheDocument()
  })

  it('stays out of the way when there is nothing to compare against', async () => {
    api.fetchWorkouts.mockResolvedValue({ items: [RIDE], total: 1, limit: 50, offset: 0 })
    const { container } = render(<CompareActivities workout={RIDE} userId={1} />)

    await waitFor(() => expect(api.fetchWorkouts).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('draws both once a second activity is chosen', async () => {
    render(<CompareActivities workout={RIDE} userId={1} />)
    await screen.findByRole('option', { name: /Same loop, faster/ })

    await userEvent.selectOptions(screen.getByLabelText(/against/i), '2')

    expect(await screen.findByText(/speed over distance/i)).toBeVisible()
    expect(screen.getByText(/elevation over distance/i)).toBeVisible()
    await waitFor(() => expect(api.fetchTrackPoints).toHaveBeenCalledWith(2, 1))
  })

  it('puts the two sets of figures side by side', async () => {
    render(<CompareActivities workout={RIDE} userId={1} />)
    await screen.findByRole('option', { name: /Same loop, faster/ })

    await userEvent.selectOptions(screen.getByLabelText(/against/i), '2')
    await screen.findByText(/speed over distance/i)

    // 20 km in 1h00 against 20 km in 53m20.
    expect(screen.getByText('1h 00m')).toBeInTheDocument()
    expect(screen.getByText('53m 20s')).toBeInTheDocument()
  })

  it('reports a second activity it cannot load', async () => {
    render(<CompareActivities workout={RIDE} userId={1} />)
    await screen.findByRole('option', { name: /Same loop, faster/ })
    api.fetchTrackPoints.mockRejectedValue(new Error('Workout not found'))

    await userEvent.selectOptions(screen.getByLabelText(/against/i), '2')

    expect(await screen.findByRole('alert')).toHaveTextContent('Workout not found')
  })

  it('clears the comparison when the choice is taken back', async () => {
    render(<CompareActivities workout={RIDE} userId={1} />)
    await screen.findByRole('option', { name: /Same loop, faster/ })
    await userEvent.selectOptions(screen.getByLabelText(/against/i), '2')
    await screen.findByText(/speed over distance/i)

    await userEvent.selectOptions(screen.getByLabelText(/against/i), '')

    expect(screen.queryByText(/speed over distance/i)).not.toBeInTheDocument()
  })

  it('asks only for activities of this sport', async () => {
    api.fetchWorkouts.mockResolvedValue({ items: [A_RUN], total: 1, limit: 50, offset: 0 })
    render(<CompareActivities workout={{ ...RIDE, sport_type: 'running' }} userId={1} />)

    await waitFor(() =>
      expect(api.fetchWorkouts).toHaveBeenCalledWith(
        expect.objectContaining({ sportType: 'running' }),
      ),
    )
  })
})
