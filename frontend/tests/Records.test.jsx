import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Records from '../src/components/Records'
import YearlyTotals from '../src/components/YearlyTotals'

function holder(overrides = {}) {
  return {
    workout_id: 3,
    workout_name: 'Long ride',
    start_time: '2026-05-30T08:45:00Z',
    utc_offset_minutes: null,
    value: 51_884,
    ...overrides,
  }
}

const RUNNING = {
  sport_type: 'running',
  workout_count: 10,
  longest_distance: holder({ workout_id: 6, workout_name: 'Half', value: 21_100 }),
  longest_duration: holder({ workout_id: 6, workout_name: 'Half', value: 7_200 }),
  biggest_climb: holder({ workout_id: 9, workout_name: 'Hill repeats', value: 583 }),
  distance_bests: [
    {
      label: '1 km',
      distance_m: 1_000,
      duration_s: 250,
      workout_id: 14,
      workout_name: 'Easy run',
      start_time: '2026-06-11T18:15:00Z',
      utc_offset_minutes: null,
    },
    {
      label: '5 km',
      distance_m: 5_000,
      duration_s: 1_350,
      workout_id: 14,
      workout_name: 'Easy run',
      start_time: '2026-06-11T18:15:00Z',
      utc_offset_minutes: null,
    },
  ],
}

const CYCLING = {
  sport_type: 'cycling',
  workout_count: 8,
  longest_distance: holder(),
  longest_duration: holder({ value: 7_260 }),
  biggest_climb: holder({ value: 481 }),
  distance_bests: [],
}

describe('Records', () => {
  it('shows each sport with the figure and the activity behind it', () => {
    render(<Records bySport={[RUNNING]} onOpenWorkout={vi.fn()} />)

    expect(screen.getByText('21.1 km')).toBeInTheDocument()
    expect(screen.getByText('2h 00m')).toBeInTheDocument()
    expect(screen.getByText('583 m')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Half · / })).toHaveLength(2)
  })

  it('names the sport in text, not by its colour alone', () => {
    render(<Records bySport={[RUNNING, CYCLING]} onOpenWorkout={vi.fn()} />)

    const sports = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)

    expect(sports.some((text) => text.includes('Running'))).toBe(true)
    expect(sports.some((text) => text.includes('Cycling'))).toBe(true)
  })

  it('gives each best a pace, in the unit the sport reads', () => {
    // A runner reads minutes per kilometre; the same helper the table uses
    // would give a cyclist km/h.
    render(<Records bySport={[RUNNING]} onOpenWorkout={vi.fn()} />)

    expect(screen.getByText('4:10 /km')).toBeInTheDocument()
    expect(screen.getByText('4:30 /km')).toBeInTheDocument()
    expect(screen.getByText('22m 30s')).toBeInTheDocument()
  })

  it('gives a cyclist speed rather than pace', () => {
    const best = {
      label: '10 km',
      distance_m: 10_000,
      duration_s: 1_200,
      workout_id: 3,
      workout_name: 'Long ride',
      start_time: '2026-05-30T08:45:00Z',
      utc_offset_minutes: null,
    }
    render(<Records bySport={[{ ...CYCLING, distance_bests: [best] }]} onOpenWorkout={vi.fn()} />)

    expect(screen.getByText('30.0 km/h')).toBeInTheDocument()
  })

  it('opens the activity that holds a record', async () => {
    const onOpenWorkout = vi.fn()
    render(<Records bySport={[RUNNING]} onOpenWorkout={onOpenWorkout} />)

    await userEvent.click(screen.getAllByRole('button', { name: /Easy run · / })[0])

    expect(onOpenWorkout).toHaveBeenCalledWith(14)
  })

  it('still shows a record when nothing can be opened', () => {
    // No handler is not an error: the figures are the point, the link is not.
    render(<Records bySport={[RUNNING]} />)

    expect(screen.getByText('21.1 km')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('omits the distance table for a sport with no stored windows', () => {
    render(<Records bySport={[CYCLING]} onOpenWorkout={vi.fn()} />)

    expect(screen.getByText('51.9 km')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('shows a dash for a record nothing qualifies for', () => {
    const sparse = { ...CYCLING, biggest_climb: null }
    render(<Records bySport={[sparse]} onOpenWorkout={vi.fn()} />)

    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('says so when there is nothing to compare yet', () => {
    render(<Records bySport={[]} onOpenWorkout={vi.fn()} />)

    expect(screen.getByText(/no records yet/i)).toBeInTheDocument()
  })

  it('survives a first render before the request has answered', () => {
    render(<Records onOpenWorkout={vi.fn()} />)

    expect(screen.getByText(/no records yet/i)).toBeInTheDocument()
  })
})

describe('YearlyTotals', () => {
  const YEARS = [
    {
      year: 2026,
      workout_count: 22,
      total_distance: 312_794,
      total_time: 74_100,
      total_elevation_gain: 7_326,
    },
    {
      year: 2025,
      workout_count: 8,
      total_distance: 90_000,
      total_time: 20_000,
      total_elevation_gain: 1_200,
    },
  ]

  it('lists the years the API sent, in the order it sent them', () => {
    // Newest first is decided by the API; re-sorting here would be a second
    // opinion that could disagree with it.
    render(<YearlyTotals years={YEARS} />)

    const rows = screen.getAllByRole('rowheader').map((cell) => cell.textContent)

    expect(rows).toEqual(['2026', '2025'])
  })

  it('totals each year in the units the rest of the dashboard uses', () => {
    render(<YearlyTotals years={YEARS} />)

    expect(screen.getByText('312.8 km')).toBeInTheDocument()
    expect(screen.getByText('20h 35m')).toBeInTheDocument()
    expect(screen.getByText('7326 m')).toBeInTheDocument()
  })

  it('says so when nothing has been recorded', () => {
    render(<YearlyTotals years={[]} />)

    expect(screen.getByText(/nothing recorded yet/i)).toBeInTheDocument()
  })
})
