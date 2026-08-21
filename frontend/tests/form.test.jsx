import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import FormChart from '../src/components/FormChart'

function series(days) {
  return days.map(([day, load, fitness, fatigue, form]) => ({
    day,
    load,
    fitness,
    fatigue,
    form,
  }))
}

const SUMMARY = {
  user_id: 1,
  max_heart_rate: 190,
  max_heart_rate_source: 'observed',
  days: 90,
  series: series([
    ['2026-06-01', 180, 42.1, 61.4, -14.2],
    ['2026-06-02', 0, 41.1, 53.2, -19.3],
    ['2026-06-03', 0, 40.2, 46.1, 12.6],
  ]),
  warmup_days: 120,
  untracked_activities: 0,
}

function show(overrides = {}, props = {}) {
  const onDaysChange = vi.fn()
  render(
    <FormChart
      summary={{ ...SUMMARY, ...overrides }}
      days={90}
      onDaysChange={onDaysChange}
      {...props}
    />,
  )
  return { onDaysChange }
}

describe('FormChart', () => {
  it('leads with where you are today, not with the whole window', () => {
    show()

    // The last day of the series is today, and "how am I now" is a number, not
    // something to read off the right-hand end of a line.
    expect(screen.getByText('40')).toBeVisible()
    expect(screen.getByText('46')).toBeVisible()
    expect(screen.getByText('+13')).toBeVisible()
  })

  it('names all three series, so identity is never colour alone', () => {
    show()

    for (const label of ['Fitness', 'Fatigue', 'Form']) {
      expect(screen.getByText(label)).toBeVisible()
    }
  })

  it('says what each average is, so the numbers are not magic', () => {
    show()

    expect(screen.getByText('42-day average')).toBeVisible()
    expect(screen.getByText('7-day average')).toBeVisible()
    expect(screen.getByText('fitness − fatigue')).toBeVisible()
  })

  it('signs form both ways, because minus eight and eight read alike', () => {
    show({ series: series([['2026-06-03', 0, 30, 45, -15]]) })

    expect(screen.getByText('-15')).toBeVisible()
  })

  it('warns when the window is climbing out of nothing', () => {
    show({ warmup_days: 0 })

    expect(screen.getByText(/climb out of zero/i)).toBeVisible()
  })

  it('stays quiet about the ramp once there is history behind the window', () => {
    show({ warmup_days: 200 })

    expect(screen.queryByText(/climb out of zero/i)).not.toBeInTheDocument()
  })

  it('owns up to the activities that earned no load', () => {
    show({ untracked_activities: 3 })

    // Not merely missing: an activity with no strap reads as a rest day, which
    // lowers fatigue and lifts form.
    expect(screen.getByText(/3 activities in this window recorded no heart rate/i)).toBeVisible()
    expect(screen.getByText(/read here as rest days/i)).toBeVisible()
  })

  it('counts one of them in the singular', () => {
    show({ untracked_activities: 1 })

    expect(screen.getByText(/1 activity in this window/i)).toBeVisible()
  })

  it('asks for a different window when one is chosen', async () => {
    const { onDaysChange } = show()

    await userEvent.selectOptions(screen.getByRole('combobox'), '365')

    expect(onDaysChange).toHaveBeenCalledWith(365)
  })

  it('explains itself rather than showing an empty frame with no strap', () => {
    show({ series: [], max_heart_rate: null })

    expect(screen.getByText(/no heart rate recorded yet/i)).toBeVisible()
  })

  it('distinguishes "no strap" from "no load yet"', () => {
    show({ series: [], max_heart_rate: 190 })

    expect(screen.getByText(/no training load yet/i)).toBeVisible()
  })

  it('survives having been given nothing at all', () => {
    render(<FormChart summary={null} days={90} onDaysChange={() => {}} />)

    expect(screen.getByText(/no heart rate recorded yet/i)).toBeVisible()
  })
})
