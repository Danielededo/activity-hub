import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../src/App'
import * as api from '../src/api/client'

vi.mock('../src/api/client', async (importOriginal) =>
  (await import('./mockClient')).mockClient(importOriginal),
)

const PROFILE = { id: 1, first_name: 'Daniele', last_name: 'De Dominicis', full_name: 'Daniele De Dominicis' }

function stubDashboard() {
  api.fetchAnalysis.mockResolvedValue({
    user_id: 1,
    workout_count: 0,
    total_distance: 0,
    total_time: 0,
    total_elevation_gain: 0,
    avg_distance: 0,
    avg_duration: 0,
    avg_heart_rate: null,
    max_heart_rate: null,
    by_sport: [],
  })
  api.fetchWeekly.mockResolvedValue({ user_id: 1, weeks: 12, buckets: [] })
  api.fetchWorkouts.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 })
  api.fetchRecords.mockResolvedValue({ user_id: 1, by_sport: [], yearly: [] })
}

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    stubDashboard()
  })

  it('asks who you are when no profile exists', async () => {
    // A 404 from /users/me is not an error: it is the first-run signal.
    api.fetchProfile.mockResolvedValue(null)

    render(<App />)

    expect(await screen.findByRole('heading', { name: /welcome to activity hub/i })).toBeVisible()
    expect(screen.getByLabelText(/first name/i)).toBeInTheDocument()
  })

  it('goes straight to the dashboard when a profile exists', async () => {
    api.fetchProfile.mockResolvedValue(PROFILE)

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Activity Hub' })).toBeVisible()
    expect(screen.getByText('Daniele De Dominicis')).toBeInTheDocument()
  })

  it('reports an unreachable API instead of showing an empty dashboard', async () => {
    api.fetchProfile.mockRejectedValue(new Error('Network Error'))

    render(<App />)

    expect(await screen.findByRole('heading', { name: /cannot reach the api/i })).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent('Network Error')
  })

  it.each([
    ['the first-run screen', () => api.fetchProfile.mockResolvedValue(null)],
    ['the dashboard', () => api.fetchProfile.mockResolvedValue(PROFILE)],
    // The one that earns the shell: somebody whose stack will not come up is
    // exactly the person who wants the repository, and this is where they stop.
    ['the unreachable-API screen', () => api.fetchProfile.mockRejectedValue(new Error('nope'))],
  ])('shows where the project lives on %s', async (_name, arrange) => {
    arrange()

    render(<App />)

    await waitFor(() => expect(screen.getByRole('contentinfo')).toBeVisible())
    expect(screen.getByRole('link', { name: /source on github/i })).toBeVisible()
  })

  it('moves on to the dashboard once the profile is created', async () => {
    api.fetchProfile.mockResolvedValue(null)
    api.createProfile.mockResolvedValue(PROFILE)

    render(<App />)
    await screen.findByRole('heading', { name: /welcome to activity hub/i })

    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/first name/i), 'Daniele')
    await user.click(screen.getByRole('button', { name: /get started/i }))

    await waitFor(() => expect(api.createProfile).toHaveBeenCalledWith({
      firstName: 'Daniele',
      lastName: '',
    }))
    expect(await screen.findByRole('heading', { name: 'Activity Hub' })).toBeVisible()
  })
})
