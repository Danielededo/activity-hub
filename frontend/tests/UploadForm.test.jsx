import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import UploadForm from '../src/components/UploadForm'
import * as api from '../src/api/client'

vi.mock('../src/api/client', () => ({
  uploadWorkout: vi.fn(),
  uploadArchive: vi.fn(),
  errorMessage: (error, fallback) => error?.response?.data?.detail ?? fallback,
}))

const file = (name) => new File(['<gpx/>'], name, { type: 'application/xml' })
const zip = (name = 'export.zip') => new File(['PK\x03\x04'], name, { type: 'application/zip' })
const empty = (name) => new File([], name, { type: 'application/xml' })

function archiveResult(overrides = {}) {
  return { stored: 0, duplicates: 0, skipped: 0, failed: 0, members: [], truncated: false, ...overrides }
}

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


// -- archives ------------------------------------------------------------

describe('UploadForm with an archive', () => {
  beforeEach(() => vi.clearAllMocks())

  it('sends a zip to the archive endpoint, not the single-file one', async () => {
    api.uploadArchive.mockResolvedValue(archiveResult({ stored: 22, skipped: 2 }))
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), zip())

    expect(api.uploadArchive).toHaveBeenCalledOnce()
    expect(api.uploadWorkout).not.toHaveBeenCalled()
  })

  it('summarises the archive instead of listing every file in it', async () => {
    // Nobody reads three hundred lines saying "added".
    api.uploadArchive.mockResolvedValue(
      archiveResult({
        stored: 22,
        duplicates: 1,
        skipped: 2,
        members: Array.from({ length: 25 }, (_, i) => ({
          filename: `a-${i}.gpx`,
          outcome: 'stored',
          workout_id: i,
        })),
      }),
    )
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), zip())

    expect(await screen.findByText(/22 added, 1 already here, 2 skipped/)).toBeVisible()
    expect(screen.queryByText('a-0.gpx')).not.toBeInTheDocument()
  })

  it('does list the members that failed, since those need attention', async () => {
    api.uploadArchive.mockResolvedValue(
      archiveResult({
        stored: 2,
        failed: 1,
        members: [
          { filename: 'good.gpx', outcome: 'stored', workout_id: 1 },
          { filename: 'broken.gpx', outcome: 'failed', detail: 'Malformed XML' },
        ],
      }),
    )
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), zip())

    expect(await screen.findByText(/export\.zip → broken\.gpx/)).toBeVisible()
    expect(screen.getByText(/Malformed XML/)).toBeVisible()
  })

  it('counts the activities in an archive, not the rows shown for it', async () => {
    // One row can stand for hundreds of activities. A summary reading
    // "1 added" after importing an export of 22 is worse than none.
    api.uploadArchive.mockResolvedValue(
      archiveResult({ stored: 22, skipped: 1, failed: 1, members: [] }),
    )
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), zip())

    expect(await screen.findByRole('status')).toHaveTextContent(
      '22 added · 1 skipped · 1 rejected',
    )
  })

  it('refreshes the dashboard when an archive stored anything', async () => {
    api.uploadArchive.mockResolvedValue(archiveResult({ stored: 5 }))
    const onUploaded = vi.fn()
    render(<UploadForm userId={1} onUploaded={onUploaded} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), zip())

    await waitFor(() => expect(onUploaded).toHaveBeenCalledOnce())
  })

  it('does not refresh when an archive imported nothing', async () => {
    api.uploadArchive.mockResolvedValue(archiveResult({ duplicates: 3 }))
    const onUploaded = vi.fn()
    render(<UploadForm userId={1} onUploaded={onUploaded} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), zip())

    const summary = await screen.findByRole('status')
    expect(summary).toHaveTextContent('3 already here')
    expect(onUploaded).not.toHaveBeenCalled()
  })
})

// -- what never reaches the network -------------------------------------

describe('UploadForm pre-checks', () => {
  beforeEach(() => vi.clearAllMocks())

  it('refuses a file that is not an activity or an archive', async () => {
    // Dropped, not picked: the input's `accept` already filters the picker, so
    // drag and drop is the path where this check actually earns its place.
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    fireEvent.drop(screen.getByTestId('dropzone'), {
      dataTransfer: { files: [file('notes.pdf')] },
    })

    expect(await screen.findByText(/not a \.tcx, \.gpx or \.zip/)).toBeVisible()
    expect(api.uploadWorkout).not.toHaveBeenCalled()
  })

  it('refuses an empty file without asking the server', async () => {
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), empty('ride.gpx'))

    expect(await screen.findByText(/the file is empty/)).toBeVisible()
    expect(api.uploadWorkout).not.toHaveBeenCalled()
  })

  it('lets the picker filter by extension, so that path needs no check', () => {
    // Documenting the division of labour: `accept` handles the picker, the
    // precheck handles everything dropped on the zone.
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    expect(screen.getByLabelText(/activity files/i)).toHaveAttribute(
      'accept',
      '.tcx,.gpx,.zip',
    )
  })

  it('still uploads the good files in a mixed drop', async () => {
    api.uploadWorkout.mockResolvedValue({ id: 1, name: 'Ride' })
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    fireEvent.drop(screen.getByTestId('dropzone'), {
      dataTransfer: { files: [file('notes.pdf'), file('ride.gpx')] },
    })

    expect(await screen.findByText('Added')).toBeVisible()
    expect(screen.getByText(/not a \.tcx/)).toBeVisible()
    expect(api.uploadWorkout).toHaveBeenCalledOnce()
  })
})

// -- progress ------------------------------------------------------------

describe('UploadForm progress', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows each result as it lands, not at the end of the batch', async () => {
    // The whole point: a few hundred files used to mean minutes of silence,
    // which is indistinguishable from a hang.
    let releaseSecond
    api.uploadWorkout
      .mockResolvedValueOnce({ id: 1, name: 'First' })
      .mockImplementationOnce(() => new Promise((resolve) => { releaseSecond = resolve }))
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), [
      file('a.gpx'),
      file('b.gpx'),
    ])

    // First one visible while the second is still in flight.
    expect(await screen.findByText('a.gpx')).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('Uploading 1 of 2')

    await act(async () => releaseSecond({ id: 2, name: 'Second' }))
    expect(await screen.findByText('b.gpx')).toBeVisible()
  })

  it('counts the batch rather than just saying "uploading"', async () => {
    const pending = []
    api.uploadWorkout.mockImplementation(
      () => new Promise((resolve) => pending.push(resolve)),
    )
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), [
      file('a.gpx'),
      file('b.gpx'),
      file('c.gpx'),
    ])

    expect(await screen.findByText(/Uploading 0 of 3/)).toBeVisible()

    // Drain inside act, or React logs an update after the test has finished.
    await act(async () => {
      pending.forEach((resolve, index) => resolve({ id: index, name: 'One' }))
    })
  })

  it('ends with a summary of the batch', async () => {
    api.uploadWorkout
      .mockResolvedValueOnce({ id: 1, name: 'One' })
      .mockRejectedValueOnce(rejectWith(409, 'Already stored as workout 1'))
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/activity files/i), [
      file('a.gpx'),
      file('b.gpx'),
    ])

    expect(await screen.findByText('1 added · 1 already here')).toBeVisible()
  })
})

// -- other ways in ------------------------------------------------------

describe('UploadForm entry points', () => {
  beforeEach(() => vi.clearAllMocks())

  it('accepts dropped files', async () => {
    api.uploadWorkout.mockResolvedValue({ id: 1, name: 'Ride' })
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    const dropped = file('ride.gpx')
    fireEvent.drop(screen.getByTestId('dropzone'), { dataTransfer: { files: [dropped] } })

    expect(await screen.findByText('Added')).toBeVisible()
    expect(api.uploadWorkout).toHaveBeenCalledWith(1, dropped)
  })

  it('offers a folder picker, for an export that was already unzipped', async () => {
    api.uploadWorkout.mockResolvedValue({ id: 1, name: 'Ride' })
    render(<UploadForm userId={1} onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/activity folder/i), file('ride.gpx'))

    expect(await screen.findByText('Added')).toBeVisible()
  })
})
