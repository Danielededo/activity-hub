import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import WorkoutTable from '../src/components/WorkoutTable'

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
}

const RUN = {
  ...RIDE,
  id: 2,
  name: 'Easy run',
  sport_type: 'running',
  start_time: '2026-06-23T05:15:00Z',
  total_distance: 10_000,
  total_time: 3_000,
}

function renderTable(props = {}) {
  return render(
    <WorkoutTable
      workouts={[RIDE, RUN]}
      total={2}
      limit={20}
      offset={0}
      onPage={vi.fn()}
      onOpen={vi.fn()}
      onDelete={vi.fn()}
      {...props}
    />,
  )
}

describe('WorkoutTable', () => {
  it('shows speed for a ride and pace for a run', () => {
    // Cyclists read km/h and runners read min/km; showing one to both would
    // make somebody do arithmetic.
    renderTable()

    expect(screen.getByText('30.0 km/h')).toBeInTheDocument()
    expect(screen.getByText('5:00 /km')).toBeInTheDocument()
  })

  it('shows each activity in its own local time', () => {
    // 06:30 UTC at +02:00 was half past eight where the ride happened.
    renderTable()

    expect(screen.getByText('08:30')).toBeInTheDocument()
    expect(screen.getByText('07:15')).toBeInTheDocument()
  })

  it('opens an activity by name', async () => {
    const onOpen = vi.fn()
    renderTable({ onOpen })

    await userEvent.click(screen.getByRole('button', { name: 'Morning ride' }))

    expect(onOpen).toHaveBeenCalledWith(RIDE)
  })

  it('labels each delete button with what it deletes', async () => {
    const onDelete = vi.fn()
    renderTable({ onDelete })

    await userEvent.click(screen.getByRole('button', { name: 'Delete Easy run' }))

    expect(onDelete).toHaveBeenCalledWith(RUN)
  })

  it('names every sport in text, never by colour alone', () => {
    renderTable()

    expect(screen.getByText('Cycling')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('invites a first upload when there is nothing yet', () => {
    renderTable({ workouts: [], total: 0 })

    expect(screen.getByText(/no activities yet/i)).toBeInTheDocument()
  })

  it('hides paging when everything fits on one page', () => {
    renderTable()

    expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument()
  })

  it('pages forward when there is more', async () => {
    const onPage = vi.fn()
    renderTable({ total: 45, onPage })

    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    expect(onPage).toHaveBeenCalledWith(20)
  })
})
