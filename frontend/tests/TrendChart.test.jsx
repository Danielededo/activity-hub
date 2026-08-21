import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import TrendChart from '../src/components/TrendChart'

const BUCKETS = [
  { week_start: '2026-06-15', iso_year: 2026, iso_week: 25, workout_count: 4, total_distance: 58_100, total_time: 14_400, total_elevation_gain: 500 },
  { week_start: '2026-06-22', iso_year: 2026, iso_week: 26, workout_count: 4, total_distance: 65_000, total_time: 16_200, total_elevation_gain: 610 },
]

describe('TrendChart', () => {
  it('titles the single measure it plots, so no legend is needed', () => {
    render(<TrendChart buckets={BUCKETS} weeks={12} onWeeksChange={vi.fn()} />)

    expect(screen.getByRole('heading', { name: /weekly distance/i })).toBeVisible()
  })

  it('lets the range be changed', async () => {
    const onWeeksChange = vi.fn()
    render(<TrendChart buckets={BUCKETS} weeks={12} onWeeksChange={onWeeksChange} />)

    await userEvent.selectOptions(screen.getByRole('combobox', { name: /range/i }), '26')

    expect(onWeeksChange).toHaveBeenCalledWith(26)
  })

  it('survives an empty history', () => {
    render(<TrendChart buckets={[]} weeks={12} onWeeksChange={vi.fn()} />)

    expect(screen.getByRole('heading', { name: /weekly distance/i })).toBeVisible()
  })

  it('does not fall over before the data arrives', () => {
    render(<TrendChart buckets={undefined} weeks={8} onWeeksChange={vi.fn()} />)

    expect(screen.getByRole('combobox', { name: /range/i })).toHaveValue('8')
  })
})
