import { useEffect, useState } from 'react'
import { errorMessage, fetchTrackPoints, fetchWorkouts } from '../api/client'
import CompareChart from './CompareChart'
import { seriesColors } from '../theme'
import { useColorScheme } from '../hooks/useColorScheme'
import {
  formatDate,
  formatDistance,
  formatDuration,
  formatRate,
  formatSpeed,
} from '../utils/formatters'
import { distanceSeries } from '../utils/track'

/**
 * Put a second activity next to this one, on a shared distance axis.
 *
 * Same sport only. Comparing a run against a ride on a distance axis is
 * arithmetic nobody asked a question about, and offering it invites the
 * comparison rather than the pace of it.
 */
export default function CompareActivities({ workout, userId }) {
  const dark = useColorScheme()
  const [candidates, setCandidates] = useState([])
  const [otherId, setOtherId] = useState('')
  // The loaded comparison, tagged with the id it belongs to, and whatever went
  // wrong last. "Loading" is not stored: it is what "an id is chosen and the
  // result is not for it yet" means, and storing it would mean setting state in
  // an effect body to say something already knowable.
  const [loaded, setLoaded] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchWorkouts({ userId, limit: 50, sportType: workout.sport_type })
      .then((page) => {
        if (!cancelled) {
          setCandidates(page.items.filter((item) => item.id !== workout.id))
        }
      })
      .catch(() => {
        // Nothing to offer is not an error worth a banner over the activity.
        if (!cancelled) setCandidates([])
      })
    return () => {
      cancelled = true
    }
  }, [userId, workout.id, workout.sport_type])

  useEffect(() => {
    if (!otherId) return undefined
    let cancelled = false
    Promise.all([
      fetchTrackPoints(workout.id, userId),
      fetchTrackPoints(Number(otherId), userId),
    ])
      .then(([mine, theirs]) => {
        if (cancelled) return
        const other = candidates.find((item) => item.id === Number(otherId))
        setLoaded({
          id: Number(otherId),
          other,
          series: [
            { id: workout.id, name: workout.name, points: distanceSeries(mine.items) },
            {
              id: Number(otherId),
              name: other?.name ?? 'Other',
              points: distanceSeries(theirs.items),
            },
          ],
        })
      })
      .catch((caught) => {
        if (!cancelled) setError(errorMessage(caught, 'Could not load that activity'))
      })
    return () => {
      cancelled = true
    }
  }, [otherId, workout.id, workout.name, userId, candidates])

  if (!candidates.length) return null

  const colours = seriesColors(2, dark)
  const chosen = Number(otherId) || null
  const ready = chosen != null && loaded?.id === chosen ? loaded : null
  const loading = chosen != null && !ready && !error

  return (
    <section className="mt-6 border-t border-[var(--border)] pt-4" aria-labelledby="compare-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="compare-heading" className="text-xs font-semibold uppercase tracking-wide muted">
          Compare
        </h3>
        <label className="text-xs muted">
          Against{' '}
          <select
            className="rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-xs"
            value={otherId}
            onChange={(event) => {
              setError(null)
              setOtherId(event.target.value)
            }}
          >
            <option value="">Nothing</option>
            {candidates.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {formatDate(item.start_time)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading && (
        <p className="mt-3 text-sm muted" role="status">
          Loading the other activity…
        </p>
      )}

      {error && (
        <p className="mt-3 text-sm text-red-700 dark:text-red-400" role="alert">
          {error}
        </p>
      )}

      {ready && (
        <>
          {/* Two figures stacked under one label, each carrying the colour its
              line has in the charts below. Without the dot the pair reads as
              two anonymous numbers and the reader has to guess which activity
              the second one belongs to. */}
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            {[
              [
                'Distance',
                formatDistance(workout.total_distance),
                formatDistance(ready.other?.total_distance),
              ],
              ['Time', formatDuration(workout.total_time), formatDuration(ready.other?.total_time)],
              [
                'Pace',
                formatRate(workout.sport_type, workout.total_distance / (workout.total_time || 1)),
                formatRate(
                  workout.sport_type,
                  (ready.other?.total_distance ?? 0) / (ready.other?.total_time || 1),
                ),
              ],
            ].map(([label, mine, theirs]) => (
              <div key={label}>
                <dt className="text-xs uppercase tracking-wide muted">{label}</dt>
                {[mine, theirs].map((value, index) => (
                  <dd key={index} className="flex items-center gap-1.5 tabular-nums">
                    <span
                      aria-hidden="true"
                      className="inline-block h-2 w-2 shrink-0 rounded-full"
                      style={{ background: colours[index] }}
                    />
                    {value}
                  </dd>
                ))}
              </div>
            ))}
          </dl>

          <div className="mt-4 space-y-5">
            {/* Speed, not pace, and km/h for every sport — see formatSpeed on
                why an instant is read differently from a whole activity. */}
            <CompareChart
              title="Speed over distance"
              unit="km/h"
              series={ready.series}
              dataKey="speed"
              formatValue={formatSpeed}
              formatAxis={(value) => (value * 3.6).toFixed(1)}
            />
            <CompareChart
              title="Elevation over distance"
              unit="m"
              series={ready.series}
              dataKey="elevation"
              formatValue={(value) => `${Math.round(value)} m`}
              formatAxis={(value) => String(Math.round(value))}
            />
          </div>
        </>
      )}
    </section>
  )
}
