import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from '../src/components/Dashboard'
import * as api from '../src/api/client'

vi.mock('../src/api/client', async (importOriginal) =>
  (await import('./mockClient')).mockClient(importOriginal),
)

const PROFILE = { id: 7, first_name: 'Daniele', full_name: 'Daniele De Dominicis' }

const RECORDS = {
  user_id: 7,
  by_sport: [
    {
      sport_type: 'cycling',
      workout_count: 8,
      longest_distance: {
        workout_id: 10,
        workout_name: 'Long ride',
        start_time: '2026-05-30T08:45:00Z',
        utc_offset_minutes: null,
        value: 51_884,
      },
      longest_duration: null,
      biggest_climb: null,
      distance_bests: [],
    },
  ],
  yearly: [
    {
      year: 2026,
      workout_count: 22,
      total_distance: 312_794,
      total_time: 74_100,
      total_elevation_gain: 7_326,
    },
  ],
}

const RIDE = {
  id: 10,
  name: 'Long ride',
  sport_type: 'cycling',
  source: 'strava',
  file_format: 'gpx',
  start_time: '2026-05-30T08:45:00Z',
  utc_offset_minutes: null,
  total_distance: 51_884,
  total_time: 7_260,
  total_elevation_gain: 335,
  avg_heart_rate: 134,
  avg_cadence: 84,
}

beforeEach(() => {
  vi.clearAllMocks()
  api.fetchAnalysis.mockResolvedValue({
    user_id: 7,
    workout_count: 22,
    total_distance: 312_794,
    total_time: 74_100,
    total_elevation_gain: 7_326,
    avg_distance: 14_218,
    avg_duration: 3_368,
    avg_heart_rate: 136,
    max_heart_rate: 190,
    by_sport: [],
  })
  api.fetchWeekly.mockResolvedValue({ user_id: 7, weeks: 12, buckets: [] })
  api.fetchWorkouts.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 })
  api.fetchRecords.mockResolvedValue(RECORDS)
  api.fetchTrackPoints.mockResolvedValue({
    workout_id: 10,
    total: 0,
    returned: 0,
    stride: 1,
    items: [],
  })
})

describe('Dashboard records', () => {
  it('shows the records and the yearly totals it loaded', async () => {
    render(<Dashboard profile={PROFILE} />)

    expect(await screen.findByText('51.9 km')).toBeVisible()
    expect(screen.getByRole('rowheader', { name: '2026' })).toBeVisible()
  })

  it('fetches the activity behind a record before opening it', async () => {
    // The record carries an id and a name, not the activity — the detail view
    // needs the whole thing.
    api.fetchWorkout.mockResolvedValue(RIDE)
    render(<Dashboard profile={PROFILE} />)
    await screen.findByText('51.9 km')

    await userEvent.click(screen.getByRole('button', { name: /Long ride · / }))

    await waitFor(() => expect(api.fetchWorkout).toHaveBeenCalledWith(10, 7))
    expect(await screen.findByRole('heading', { name: 'Long ride' })).toBeVisible()
  })

  it('reports a record whose activity cannot be fetched', async () => {
    api.fetchWorkout.mockRejectedValue(new Error('Workout not found'))
    render(<Dashboard profile={PROFILE} />)
    await screen.findByText('51.9 km')

    await userEvent.click(screen.getByRole('button', { name: /Long ride · / }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Workout not found')
  })

  it('renders before the records have arrived', async () => {
    // Four requests land at different times; the panel must not blow up on the
    // render that happens before its own does.
    let release
    api.fetchRecords.mockReturnValue(new Promise((resolve) => {
      release = resolve
    }))

    render(<Dashboard profile={PROFILE} />)

    expect(await screen.findByText(/no records yet/i)).toBeVisible()
    release(RECORDS)
    expect(await screen.findByText('51.9 km')).toBeVisible()
  })
})
