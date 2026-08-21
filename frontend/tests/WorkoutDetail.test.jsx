import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkoutDetail from '../src/components/WorkoutDetail'
import * as api from '../src/api/client'

vi.mock('../src/api/client', async (importOriginal) =>
  (await import('./mockClient')).mockClient(importOriginal),
)

const RIDE = {
  id: 1,
  name: 'Morning ride',
  sport_type: 'cycling',
  source: 'garmin',
  file_format: 'tcx',
  start_time: '2026-06-22T06:30:00Z',
  utc_offset_minutes: 120,
  total_distance: 30_000,
  total_time: 3_600,
  total_elevation_gain: 420,
  avg_heart_rate: 134,
  avg_cadence: 82,
}

const RUN = { ...RIDE, id: 2, name: 'Easy run', sport_type: 'running', avg_cadence: 86 }

/** Samples every trace can draw from: position, elevation, heart rate, cadence. */
function samples(count = 6, extra = {}) {
  return Array.from({ length: count }, (_, index) => ({
    sequence: index,
    timestamp: new Date(Date.UTC(2026, 5, 22, 6, 30 + index)).toISOString(),
    latitude: 45.07 + index * 0.001,
    longitude: 7.68 + index * 0.001,
    elevation: 240 + index,
    heart_rate: 130 + index,
    cadence: 80 + index,
    ...extra,
  }))
}

function series(items) {
  return { workout_id: 1, total: items.length, returned: items.length, stride: 1, items }
}

beforeEach(() => {
  vi.clearAllMocks()
  api.fetchTrackPoints.mockResolvedValue(series(samples()))
})

describe('WorkoutDetail export', () => {
  it('offers this activity as a GPX download', async () => {
    render(<WorkoutDetail workout={RIDE} userId={7} onClose={vi.fn()} />)
    // Awaited so the track and zone requests land inside the test rather than
    // updating state after it has finished.
    await screen.findByRole('heading', { name: 'Route' })

    const link = screen.getByRole('link', { name: 'GPX' })

    expect(link).toHaveAttribute('href', expect.stringContaining('/workouts/1/export.gpx'))
    expect(link.getAttribute('href')).toContain('user_id=7')
  })
})

describe('WorkoutDetail zones', () => {
  const BANDS = [
    { zone: 1, name: 'Recovery', min_bpm: 95, max_bpm: 113, seconds: 300 },
    { zone: 2, name: 'Endurance', min_bpm: 114, max_bpm: 132, seconds: 900 },
    { zone: 3, name: 'Tempo', min_bpm: 133, max_bpm: 151, seconds: 0 },
    { zone: 4, name: 'Threshold', min_bpm: 152, max_bpm: 170, seconds: 0 },
    { zone: 5, name: 'VO2 max', min_bpm: 171, max_bpm: null, seconds: 0 },
  ]

  it('shows the time in zone for this activity', async () => {
    api.fetchWorkoutZones.mockResolvedValue({
      workout_id: 1,
      max_heart_rate: 190,
      max_heart_rate_source: 'observed',
      zones: BANDS,
      seconds_below_zones: 0,
      load: 35,
    })

    render(<WorkoutDetail workout={RIDE} userId={1} onClose={vi.fn()} />)

    expect(await screen.findByText(/Z2 Endurance/)).toBeVisible()
    expect(screen.getByText('35')).toBeInTheDocument()
  })

  it('shows nothing about zones for an activity with no heart rate', async () => {
    api.fetchWorkoutZones.mockResolvedValue({
      workout_id: 1,
      max_heart_rate: null,
      max_heart_rate_source: 'unknown',
      zones: [],
      seconds_below_zones: 0,
      load: 0,
    })

    render(<WorkoutDetail workout={RIDE} userId={1} onClose={vi.fn()} />)

    await screen.findByRole('heading', { name: 'Heart rate' })
    expect(screen.queryByText(/time in zone/i)).not.toBeInTheDocument()
  })

  it('still draws the activity when the zone request fails', async () => {
    // A missing breakdown is not worth losing the traces somebody asked to see.
    api.fetchWorkoutZones.mockRejectedValue(new Error('nope'))

    render(<WorkoutDetail workout={RIDE} userId={1} onClose={vi.fn()} />)

    expect(await screen.findByRole('heading', { name: 'Heart rate' })).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('WorkoutDetail cadence', () => {
  it('reports a ride cadence in crank revolutions', async () => {
    render(<WorkoutDetail workout={RIDE} userId={1} onClose={vi.fn()} />)

    expect(await screen.findByText('82 rpm')).toBeVisible()
  })

  it('reports a run cadence in strides, not revolutions', async () => {
    // TCX RunCadence and GPX cad are written per leg, so the figure is strides
    // per minute — labelling a run "rpm" would be describing a crank.
    render(<WorkoutDetail workout={RUN} userId={1} onClose={vi.fn()} />)

    expect(await screen.findByText('86 spm')).toBeVisible()
  })

  it('draws a cadence trace alongside heart rate and elevation', async () => {
    render(<WorkoutDetail workout={RIDE} userId={1} onClose={vi.fn()} />)

    expect(await screen.findByRole('heading', { name: 'Cadence' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Heart rate' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Elevation' })).toBeVisible()
  })

  it('keeps the body measures together, terrain after', async () => {
    render(<WorkoutDetail workout={RIDE} userId={1} onClose={vi.fn()} />)
    await screen.findByRole('heading', { name: 'Cadence' })

    const titles = screen
      .getAllByRole('heading', { level: 3 })
      .map((heading) => heading.textContent)

    expect(titles).toEqual(['Route', 'Heart rate', 'Cadence', 'Elevation'])
  })

  it('draws no cadence chart for a file that recorded none', async () => {
    // A phone-recorded GPX has position and nothing else; an empty axis would
    // suggest the sensor read zero rather than that there was no sensor.
    api.fetchTrackPoints.mockResolvedValue(series(samples(6, { cadence: null })))

    render(<WorkoutDetail workout={{ ...RIDE, avg_cadence: null }} userId={1} onClose={vi.fn()} />)

    await screen.findByRole('heading', { name: 'Heart rate' })
    expect(screen.queryByRole('heading', { name: 'Cadence' })).not.toBeInTheDocument()
  })

  it('shows a dash for a missing average rather than a unit on its own', async () => {
    render(<WorkoutDetail workout={{ ...RIDE, avg_cadence: null }} userId={1} onClose={vi.fn()} />)

    await screen.findByRole('heading', { name: 'Heart rate' })
    const cadence = screen.getByText('Cadence', { selector: 'dt' })

    expect(cadence.nextSibling).toHaveTextContent('—')
  })
})
