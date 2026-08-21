import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from '../src/components/Dashboard'
import * as api from '../src/api/client'

vi.mock('../src/api/client', () => ({
  errorMessage: (error, fallback) => error?.message ?? fallback ?? 'error',
  fetchAnalysis: vi.fn(),
  fetchRecords: vi.fn(),
  fetchWeekly: vi.fn(),
  fetchWorkout: vi.fn(),
  fetchWorkouts: vi.fn(),
  deleteWorkout: vi.fn(),
  uploadWorkout: vi.fn(),
  uploadArchive: vi.fn(),
}))

const PROFILE = { id: 7, first_name: 'Daniele', full_name: 'Daniele De Dominicis' }

const BY_SPORT = [
  { sport_type: 'cycling', workout_count: 30, total_distance: 400_000, total_time: 90_000 },
  { sport_type: 'running', workout_count: 12, total_distance: 90_000, total_time: 30_000 },
]

function ride(id) {
  return {
    id,
    name: `Ride ${id}`,
    sport_type: 'cycling',
    source: 'garmin',
    file_format: 'tcx',
    start_time: '2026-07-01T06:30:00Z',
    utc_offset_minutes: 120,
    total_distance: 30_000,
    total_time: 3_600,
    total_elevation_gain: 420,
    avg_heart_rate: 134,
  }
}

/** Enough activities that paging exists, which is what filters interact with. */
function listOf(count, total = 42) {
  return {
    items: Array.from({ length: count }, (_, index) => ride(index + 1)),
    total,
    limit: 20,
    offset: 0,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  api.fetchAnalysis.mockResolvedValue({
    user_id: 7,
    workout_count: 42,
    total_distance: 490_000,
    total_time: 120_000,
    total_elevation_gain: 8_000,
    avg_distance: 11_666,
    avg_duration: 2_857,
    avg_heart_rate: 132,
    max_heart_rate: 186,
    by_sport: BY_SPORT,
  })
  api.fetchWeekly.mockResolvedValue({ user_id: 7, weeks: 12, buckets: [] })
  api.fetchRecords.mockResolvedValue({ user_id: 7, by_sport: [], yearly: [] })
  api.fetchWorkouts.mockResolvedValue(listOf(20))
})

/** The filter values of the most recent list request. */
function lastQuery() {
  const calls = api.fetchWorkouts.mock.calls
  return calls[calls.length - 1][0]
}

describe('Dashboard filtering', () => {
  it('offers the sports from the breakdown once it has loaded', async () => {
    render(<Dashboard profile={PROFILE} />)

    expect(await screen.findByRole('option', { name: 'Cycling (30)' })).toBeInTheDocument()
  })

  it('asks the server for the chosen sport', async () => {
    render(<Dashboard profile={PROFILE} />)
    await screen.findByRole('option', { name: 'Running (12)' })

    await userEvent.selectOptions(screen.getByLabelText('Sport'), 'running')

    await waitFor(() => expect(lastQuery()).toMatchObject({ sportType: 'running', offset: 0 }))
  })

  it('goes back to the first page when a filter changes', async () => {
    // Page three of the whole library is not page three of one sport, and an
    // offset past the end of a filtered result shows an empty table.
    render(<Dashboard profile={PROFILE} />)
    await screen.findByRole('option', { name: 'Running (12)' })

    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => expect(lastQuery().offset).toBe(20))

    await userEvent.selectOptions(screen.getByLabelText('Sport'), 'running')

    await waitFor(() => expect(lastQuery().offset).toBe(0))
  })

  it('does not re-request the lifetime totals when only the list narrows', async () => {
    // The cards and the trend describe all of your training; they are not part
    // of what a filter narrows, so filtering must not refetch them.
    render(<Dashboard profile={PROFILE} />)
    await screen.findByRole('option', { name: 'Running (12)' })
    expect(api.fetchAnalysis).toHaveBeenCalledTimes(1)

    await userEvent.selectOptions(screen.getByLabelText('Sport'), 'running')
    await waitFor(() => expect(lastQuery().sportType).toBe('running'))

    expect(api.fetchAnalysis).toHaveBeenCalledTimes(1)
    expect(api.fetchWeekly).toHaveBeenCalledTimes(1)
    // Records are lifetime figures as well: a filter does not narrow them.
    expect(api.fetchRecords).toHaveBeenCalledTimes(1)
  })

  it('passes a date range through', async () => {
    render(<Dashboard profile={PROFILE} />)
    await screen.findByRole('option', { name: 'Running (12)' })

    await userEvent.type(screen.getByLabelText('From'), '2026-07-01')

    await waitFor(() => expect(lastQuery().dateFrom).toBe('2026-07-01'))
  })

  it('clears back to the unfiltered list', async () => {
    render(<Dashboard profile={PROFILE} />)
    await screen.findByRole('option', { name: 'Running (12)' })

    await userEvent.selectOptions(screen.getByLabelText('Sport'), 'running')
    await waitFor(() => expect(lastQuery().sportType).toBe('running'))

    await userEvent.click(screen.getByRole('button', { name: /clear filters/i }))

    await waitFor(() => expect(lastQuery().sportType).toBe(''))
  })

  it('explains an empty filtered result instead of asking for a first upload', async () => {
    render(<Dashboard profile={PROFILE} />)
    await screen.findByRole('option', { name: 'Running (12)' })
    api.fetchWorkouts.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 })

    await userEvent.selectOptions(screen.getByLabelText('Sport'), 'running')

    expect(await screen.findByText(/no activities match these filters/i)).toBeVisible()
  })

  it('reports a failed list without blanking the whole dashboard', async () => {
    render(<Dashboard profile={PROFILE} />)
    await screen.findByRole('option', { name: 'Running (12)' })
    api.fetchWorkouts.mockRejectedValue(new Error('Request failed'))

    await userEvent.selectOptions(screen.getByLabelText('Sport'), 'running')

    expect(await screen.findByRole('alert')).toHaveTextContent('Request failed')
    expect(screen.getByRole('heading', { name: 'Activity Hub' })).toBeVisible()
  })
})

describe('Dashboard deletion', () => {
  it('deletes only after the confirmation and then reloads', async () => {
    render(<Dashboard profile={PROFILE} />)
    await screen.findByRole('button', { name: 'Delete Ride 1' })
    api.deleteWorkout.mockResolvedValue(undefined)

    await userEvent.click(screen.getByRole('button', { name: 'Delete Ride 1' }))
    expect(api.deleteWorkout).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Confirm deleting Ride 1' }))

    await waitFor(() => expect(api.deleteWorkout).toHaveBeenCalledWith(1, 7))
    // A delete changes the totals as well as the list, so both are refreshed.
    await waitFor(() => expect(api.fetchAnalysis).toHaveBeenCalledTimes(2))
  })

  it('keeps the current filter when reloading after a delete', async () => {
    render(<Dashboard profile={PROFILE} />)
    await screen.findByRole('option', { name: 'Running (12)' })
    api.deleteWorkout.mockResolvedValue(undefined)

    await userEvent.selectOptions(screen.getByLabelText('Sport'), 'running')
    await waitFor(() => expect(lastQuery().sportType).toBe('running'))

    await userEvent.click(screen.getByRole('button', { name: 'Delete Ride 1' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm deleting Ride 1' }))

    await waitFor(() => expect(api.deleteWorkout).toHaveBeenCalled())
    expect(lastQuery().sportType).toBe('running')
  })

  it('reports a refused delete', async () => {
    render(<Dashboard profile={PROFILE} />)
    await screen.findByRole('button', { name: 'Delete Ride 1' })
    api.deleteWorkout.mockRejectedValue(new Error('Workout not found'))

    await userEvent.click(screen.getByRole('button', { name: 'Delete Ride 1' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm deleting Ride 1' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Workout not found')
  })
})
