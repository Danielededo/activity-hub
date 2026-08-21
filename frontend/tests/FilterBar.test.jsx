import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import FilterBar, { EMPTY_FILTERS, hasFilters } from '../src/components/FilterBar'

const SPORTS = [
  { sport_type: 'cycling', workout_count: 12, total_distance: 0, total_time: 0 },
  { sport_type: 'running', workout_count: 4, total_distance: 0, total_time: 0 },
]

function renderBar(props = {}) {
  const onChange = vi.fn()
  const result = render(
    <FilterBar sports={SPORTS} filters={EMPTY_FILTERS} onChange={onChange} {...props} />,
  )
  return { onChange, ...result }
}

afterEach(() => {
  vi.useRealTimers()
})

describe('hasFilters', () => {
  it('is false for the empty set', () => {
    expect(hasFilters(EMPTY_FILTERS)).toBe(false)
  })

  it('is true as soon as anything is set', () => {
    expect(hasFilters({ ...EMPTY_FILTERS, q: 'ride' })).toBe(true)
    expect(hasFilters({ ...EMPTY_FILTERS, sportType: 'cycling' })).toBe(true)
  })
})

describe('FilterBar', () => {
  it('offers only the sports that were actually recorded, with their counts', () => {
    renderBar()

    expect(screen.getByRole('option', { name: 'Cycling (12)' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Running (4)' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /hiking/i })).not.toBeInTheDocument()
  })

  it('always offers a way back to everything', () => {
    renderBar()

    expect(screen.getByRole('option', { name: 'All sports' })).toBeInTheDocument()
  })

  it('applies a sport immediately', async () => {
    const { onChange } = renderBar()

    await userEvent.selectOptions(screen.getByLabelText('Sport'), 'running')

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_FILTERS, sportType: 'running' })
  })

  it('applies a date immediately', async () => {
    const { onChange } = renderBar()

    await userEvent.type(screen.getByLabelText('From'), '2026-07-01')

    expect(onChange).toHaveBeenLastCalledWith({ ...EMPTY_FILTERS, dateFrom: '2026-07-01' })
  })

  it('stops the date pickers offering a reversed range', () => {
    renderBar({ filters: { ...EMPTY_FILTERS, dateFrom: '2026-07-01', dateTo: '2026-07-31' } })

    expect(screen.getByLabelText('From')).toHaveAttribute('max', '2026-07-31')
    expect(screen.getByLabelText('To')).toHaveAttribute('min', '2026-07-01')
  })

  it('sends one search request for a typed word, not one per keystroke', async () => {
    // fireEvent rather than userEvent: userEvent awaits real timers between
    // keystrokes, which deadlocks against the fake clock this test needs to
    // step deliberately. The typing itself is what is being simulated here,
    // not the browser's input handling.
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<FilterBar sports={SPORTS} filters={EMPTY_FILTERS} onChange={onChange} />)
    const box = screen.getByLabelText('Name contains')

    for (const typed of ['M', 'Mo', 'Mon', 'Mont', 'Monte']) {
      fireEvent.change(box, { target: { value: typed } })
    }

    expect(onChange).not.toHaveBeenCalled()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(400)
    })

    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_FILTERS, q: 'Monte' })
  })

  it('offers Clear only once something is filtered', () => {
    const { rerender } = renderBar()
    expect(screen.queryByRole('button', { name: /clear filters/i })).not.toBeInTheDocument()

    rerender(
      <FilterBar
        sports={SPORTS}
        filters={{ ...EMPTY_FILTERS, sportType: 'cycling' }}
        onChange={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: /clear filters/i })).toBeVisible()
  })

  it('clears everything at once, the search box included', async () => {
    const onChange = vi.fn()
    render(
      <FilterBar
        sports={SPORTS}
        filters={{ sportType: 'cycling', dateFrom: '2026-07-01', dateTo: '', q: 'ride' }}
        onChange={onChange}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: /clear filters/i }))

    expect(onChange).toHaveBeenCalledWith(EMPTY_FILTERS)
    expect(screen.getByLabelText('Name contains')).toHaveValue('')
  })

  it('can be disabled as a whole', () => {
    renderBar({ disabled: true })

    expect(screen.getByLabelText('Sport')).toBeDisabled()
    expect(screen.getByLabelText('Name contains')).toBeDisabled()
  })
})
