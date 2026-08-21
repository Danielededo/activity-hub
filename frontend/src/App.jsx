import { useEffect, useState } from 'react'
import { errorMessage, fetchProfile } from './api/client'
import Dashboard from './components/Dashboard'
import FirstRunScreen from './components/FirstRunScreen'

/**
 * Decides between the first-run screen and the dashboard.
 *
 * A 404 from /users/me is not an error: it means nobody has introduced
 * themselves yet, which is exactly what the first-run screen is for.
 */
export default function App() {
  const [state, setState] = useState({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    fetchProfile()
      .then((profile) => {
        if (!cancelled) setState({ status: 'ready', profile })
      })
      .catch((caught) => {
        if (!cancelled) setState({ status: 'error', message: errorMessage(caught) })
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (state.status === 'loading') {
    return (
      <p className="p-8 text-sm text-slate-600 dark:text-slate-400" role="status">
        Loading…
      </p>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="mx-auto max-w-md p-8">
        <h1 className="text-lg font-semibold">Cannot reach the API</h1>
        <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-400">
          {state.message}
        </p>
      </div>
    )
  }

  if (!state.profile) {
    return <FirstRunScreen onCreated={(profile) => setState({ status: 'ready', profile })} />
  }

  return <Dashboard profile={state.profile} />
}
