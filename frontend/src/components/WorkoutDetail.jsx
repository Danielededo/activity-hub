import { useEffect, useState } from 'react'
import { errorMessage, exportUrl, fetchTrackPoints, fetchWorkoutZones } from '../api/client'
import RouteMap from './RouteMap'
import TraceChart from './TraceChart'
import ZoneBar from './ZoneBar'
import {
  cadenceUnit,
  formatCadence,
  formatDistance,
  formatDuration,
  formatElevation,
  formatHeartRate,
  formatPaceOrSpeed,
  sportLabel,
} from '../utils/formatters'

/** Turn samples into something the charts can plot along one x axis. */
function withElapsed(items) {
  const timestamps = items.map((item) => item.timestamp).filter(Boolean)
  const start = timestamps.length ? new Date(timestamps[0]).getTime() : null

  return {
    timed: start != null,
    samples: items.map((item, index) => ({
      ...item,
      elapsed:
        start != null && item.timestamp
          ? (new Date(item.timestamp).getTime() - start) / 1000
          : index,
    })),
  }
}

export default function WorkoutDetail({ workout, userId, onClose }) {
  const [series, setSeries] = useState(null)
  const [zones, setZones] = useState(null)
  const [error, setError] = useState(null)

  // No state reset here: Dashboard gives this component a key per workout, so
  // switching activities remounts it with fresh state instead of cascading a
  // render to clear the old one.
  useEffect(() => {
    let cancelled = false
    fetchTrackPoints(workout.id, userId)
      .then((data) => {
        if (!cancelled) setSeries(data)
      })
      .catch((caught) => {
        if (!cancelled) setError(errorMessage(caught, 'Could not load the track'))
      })
    return () => {
      cancelled = true
    }
  }, [workout.id, userId])

  // Its own request: the zones hang off a maximum heart rate the server knows
  // and this component does not, and a track without a strap has none at all.
  useEffect(() => {
    let cancelled = false
    fetchWorkoutZones(workout.id, userId)
      .then((data) => {
        if (!cancelled) setZones(data)
      })
      .catch(() => {
        // A missing zone breakdown is not worth an error banner over the
        // activity somebody asked to see; the traces are still there.
        if (!cancelled) setZones(null)
      })
    return () => {
      cancelled = true
    }
  }, [workout.id, userId])

  const prepared = series ? withElapsed(series.items) : null
  const xFormatter = prepared?.timed ? undefined : (index) => `sample ${index}`

  return (
    <section
      className="panel p-4"
      aria-labelledby="detail-heading"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 id="detail-heading" className="text-base font-semibold">
            {workout.name}
          </h2>
          <p className="mt-1 text-xs muted">
            {sportLabel(workout.sport_type)} · {workout.source} · {workout.file_format.toUpperCase()}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <a
            className="rounded-md border border-[var(--border)] px-3 py-1 text-sm"
            href={exportUrl(`/workouts/${workout.id}/export.gpx`, { userId })}
          >
            GPX
          </a>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-[var(--border)] px-3 py-1 text-sm"
          >
            Close
          </button>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
        {[
          ['Distance', formatDistance(workout.total_distance)],
          ['Time', formatDuration(workout.total_time)],
          [
            'Pace',
            formatPaceOrSpeed(workout.sport_type, workout.total_distance, workout.total_time),
          ],
          ['Climb', formatElevation(workout.total_elevation_gain)],
          ['Heart rate', formatHeartRate(workout.avg_heart_rate)],
          ['Cadence', formatCadence(workout.avg_cadence, workout.sport_type)],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs uppercase tracking-wide muted">
              {label}
            </dt>
            <dd className="tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>

      {zones && <div className="mt-4"><ZoneBar zones={zones.zones} load={zones.load} /></div>}

      {error && (
        <p role="alert" className="mt-4 text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}

      {!series && !error && (
        <p className="mt-4 text-sm muted">Loading the track…</p>
      )}

      {prepared && (
        <div className="mt-4 grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide muted">
              Route
            </h3>
            <RouteMap samples={prepared.samples} sportType={workout.sport_type} />
            <p className="text-xs muted">
              {series.returned} of {series.total} samples
              {series.stride > 1 && ` (every ${series.stride})`}
            </p>
          </div>

          <div className="space-y-6">
            {/* Heart rate then cadence then elevation: the two measures of
                how hard the body was working sit together, and the terrain
                that explains them comes after. Each has its own chart — see
                TraceChart on why they do not share a frame. */}
            <TraceChart
              title="Heart rate"
              unit="bpm"
              dataKey="heart_rate"
              samples={prepared.samples}
              xFormatter={xFormatter}
              formatValue={(value) => `${value} bpm`}
            />
            <TraceChart
              title="Cadence"
              unit={cadenceUnit(workout.sport_type)}
              dataKey="cadence"
              samples={prepared.samples}
              xFormatter={xFormatter}
              formatValue={(value) => formatCadence(value, workout.sport_type)}
            />
            <TraceChart
              title="Elevation"
              unit="m"
              dataKey="elevation"
              samples={prepared.samples}
              xFormatter={xFormatter}
              formatValue={(value) => `${Math.round(value)} m`}
            />
          </div>
        </div>
      )}
    </section>
  )
}
