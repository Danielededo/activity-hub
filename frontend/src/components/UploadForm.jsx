import { useRef, useState } from 'react'
import { errorMessage, uploadWorkout } from '../api/client'

const ACCEPT = '.tcx,.gpx'

/**
 * Uploads one or more files, reporting each separately.
 *
 * A rejected file is not a failure of the batch: re-uploading a folder where
 * half is already stored is the normal case, so a 409 reads as "already here"
 * rather than an error.
 */
export default function UploadForm({ userId, onUploaded }) {
  const inputRef = useRef(null)
  const [results, setResults] = useState([])
  const [busy, setBusy] = useState(false)

  async function send(files) {
    if (!files.length) return
    setBusy(true)
    const collected = []
    for (const file of files) {
      try {
        const workout = await uploadWorkout(userId, file)
        collected.push({ name: file.name, state: 'stored', detail: workout.name })
      } catch (caught) {
        const status = caught?.response?.status
        collected.push({
          name: file.name,
          state: status === 409 ? 'duplicate' : 'rejected',
          detail: errorMessage(caught, 'Upload failed'),
        })
      }
    }
    setResults(collected)
    setBusy(false)
    if (collected.some((row) => row.state === 'stored')) onUploaded()
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <section
      className="panel p-4"
      aria-labelledby="upload-heading"
    >
      <h2 id="upload-heading" className="text-sm font-semibold">
        Add activities
      </h2>
      <p className="mt-1 text-xs muted">
        TCX from Garmin, GPX from Strava or Komoot. Files already stored are skipped.
      </p>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        aria-label="Activity files"
        disabled={busy}
        onChange={(event) => send(Array.from(event.target.files ?? []))}
        className="mt-3 block w-full text-sm file:mr-3 file:rounded-md file:border-0
          file:bg-sky-700 file:px-3 file:py-2 file:text-white hover:file:bg-sky-800"
      />

      {busy && <p className="mt-3 text-sm muted">Uploading…</p>}

      {results.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm" aria-live="polite">
          {results.map((row) => (
            <li key={row.name} className="flex gap-2">
              <span
                className={
                  row.state === 'stored'
                    ? 'text-green-700 dark:text-green-400'
                    : row.state === 'duplicate'
                      ? 'muted'
                      : 'text-red-700 dark:text-red-400'
                }
              >
                {row.state === 'stored' ? 'Added' : row.state === 'duplicate' ? 'Already here' : 'Rejected'}
              </span>
              <span className="truncate">{row.name}</span>
              {row.state === 'rejected' && (
                <span className="muted">— {row.detail}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
