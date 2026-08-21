import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import StatsCards from '../src/components/StatsCards'

const SUMMARY = {
  workout_count: 22,
  total_distance: 312_800,
  total_time: 74_160,
  total_elevation_gain: 7_326,
  avg_distance: 14_218,
  avg_duration: 3_371,
  avg_heart_rate: 136.4,
  max_heart_rate: 190,
}

describe('StatsCards', () => {
  it('shows lifetime totals with their averages', () => {
    render(<StatsCards summary={SUMMARY} />)

    expect(screen.getByText('22')).toBeInTheDocument()
    expect(screen.getByText('312.8 km')).toBeInTheDocument()
    expect(screen.getByText('20h 36m')).toBeInTheDocument()
    expect(screen.getByText('14.2 km on average')).toBeInTheDocument()
    expect(screen.getByText('190 bpm peak')).toBeInTheDocument()
  })

  it('renders nothing before the summary arrives', () => {
    const { container } = render(<StatsCards summary={null} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('leaves an unknown heart rate blank rather than showing a zero', () => {
    render(<StatsCards summary={{ ...SUMMARY, avg_heart_rate: null, max_heart_rate: null }} />)

    expect(screen.getByText('—')).toBeInTheDocument()
  })
})
