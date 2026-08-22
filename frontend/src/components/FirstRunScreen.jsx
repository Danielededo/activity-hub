import { useState } from 'react'
import { createProfile, errorMessage } from '../api/client'

/**
 * Shown when GET /users/me answers 404.
 *
 * The activity files cannot supply a name — GPX has a slot for it that
 * exporters leave empty, TCX has none at all — so this is the one question the
 * app has to ask, once.
 */
export default function FirstRunScreen({ onCreated }) {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      onCreated(await createProfile({ firstName: firstName.trim(), lastName: lastName.trim() }))
    } catch (caught) {
      setError(errorMessage(caught, 'Could not save the profile'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="mx-auto flex max-w-md flex-1 flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-semibold">Welcome to Activity Hub</h1>
      <p className="mt-2 text-sm muted">
        Your activity files do not carry your name, so tell us once and we will not ask again.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-4" aria-labelledby="first-run-heading">
        <h2 id="first-run-heading" className="sr-only">
          Create your profile
        </h2>

        <div>
          <label htmlFor="first-name" className="block text-sm font-medium">
            First name
          </label>
          <input
            id="first-name"
            name="first_name"
            required
            autoFocus
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2 border-[var(--border)] bg-[var(--surface-sunken)]"
          />
        </div>

        <div>
          <label htmlFor="last-name" className="block text-sm font-medium">
            Last name <span className="font-normal muted">(optional)</span>
          </label>
          <input
            id="last-name"
            name="last_name"
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2 border-[var(--border)] bg-[var(--surface-sunken)]"
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={saving || !firstName.trim()}
          className="w-full rounded-md bg-sky-700 px-4 py-2 font-medium text-white
            hover:bg-sky-800 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Get started'}
        </button>
      </form>
    </main>
  )
}
