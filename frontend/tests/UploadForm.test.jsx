import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import UploadForm from '../src/components/UploadForm'
import * as api from '../src/api/client'

vi.mock('../src/api/client', () => ({
  uploadWorkout: vi.fn(),
  errorMessage: (error, fallback) => error?.response?.data?.detail ?? fallback,
}))

const file = (name) => new File(['<gpx/>'], name, { type: 'application/xml' })

function rejectWith(status, detail) {
  return Object.assign(new Error(detail), { response: { status, data: { detail } } })
}

describe('UploadForm', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reports a stored file and refreshes the dashboard', async () => {
    api.uploadWorkout.mockResolvedValue({ id: 1, name: 'Morning ride' })
    const onUploaded = vi.fn()
    render(<UploadForm userId={1} onUploaded={onUploaded} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), file('ride.gpx'))

    expect(await screen.findByText('Added')).toBeVisible()
    expect(onUploaded).toHaveBeenCalledOnce()
  })

  it('treats an already-stored file as normal, not as a failure', async () => {
    // Re-uploading a folder where half is present is the ordinary case.
    api.uploadWorkout.mockRejectedValue(rejectWith(409, 'Already stored as workout 3'))
    const onUploaded = vi.fn()
    render(<UploadForm userId={1} onUploaded={onUploaded} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), file('ride.gpx'))

    expect(await screen.findByText('Already here')).toBeVisible()
    expect(onUploaded).not.toHaveBeenCalled()
  })

  it('shows the reason a file was rejected', async () => {
    api.uploadWorkout.mockRejectedValue(rejectWith(422, 'Malformed XML: mismatched tag'))
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), file('broken.gpx'))

    expect(await screen.findByText('Rejected')).toBeVisible()
    expect(screen.getByText(/mismatched tag/i)).toBeInTheDocument()
  })

  it('reports each file in a batch separately', async () => {
    api.uploadWorkout
      .mockResolvedValueOnce({ id: 1, name: 'One' })
      .mockRejectedValueOnce(rejectWith(409, 'Already stored as workout 1'))
    const onUploaded = vi.fn()
    render(<UploadForm userId={1} onUploaded={onUploaded} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), [
      file('a.gpx'),
      file('b.gpx'),
    ])

    expect(await screen.findByText('Added')).toBeVisible()
    expect(screen.getByText('Already here')).toBeVisible()
    // One of the two landed, so the dashboard still needs refreshing.
    await waitFor(() => expect(onUploaded).toHaveBeenCalledOnce())
  })
})
