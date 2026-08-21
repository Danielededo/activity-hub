import {
  formatDistance,
  formatDuration,
  formatElevation,
  formatHeartRate,
} from '../utils/formatters'

/**
 * Lifetime totals as stat tiles.
 *
 * Deliberately not a chart: five unrelated single numbers have no shape to
 * show, and a chart of one value per category would just be a bar chart of
 * incomparable units.
 */
function Tile({ label, value, hint }) {
  return (
    <div className="panel p-4">
      <dt className="text-xs font-medium uppercase tracking-wide muted">
        {label}
      </dt>
      <dd className="mt-1 text-2xl font-semibold tabular-nums">{value}</dd>
      {hint && <p className="mt-1 text-xs muted">{hint}</p>}
    </div>
  )
}

export default function StatsCards({ summary }) {
  if (!summary) return null

  return (
    <dl className="grid grid-cols-2 gap-4 lg:grid-cols-5">
      <Tile label="Activities" value={summary.workout_count} />
      <Tile
        label="Distance"
        value={formatDistance(summary.total_distance)}
        hint={`${formatDistance(summary.avg_distance)} on average`}
      />
      <Tile
        label="Moving time"
        value={formatDuration(summary.total_time)}
        hint={`${formatDuration(summary.avg_duration)} on average`}
      />
      <Tile label="Elevation" value={formatElevation(summary.total_elevation_gain)} />
      <Tile
        label="Heart rate"
        value={formatHeartRate(summary.avg_heart_rate)}
        hint={summary.max_heart_rate ? `${summary.max_heart_rate} bpm peak` : undefined}
      />
    </dl>
  )
}
