import { sportColor } from '../theme'
import { useColorScheme } from '../hooks/useColorScheme'
import {
  formatDate,
  formatDistance,
  formatDuration,
  formatElevation,
  formatHeartRate,
  formatLocalTime,
  formatPaceOrSpeed,
  sportLabel,
} from '../utils/formatters'

/** The table view: every activity, in numbers, not colour. */
export default function WorkoutTable({ workouts, total, limit, offset, onPage, onOpen, onDelete }) {
  const dark = useColorScheme()

  if (!workouts?.length) {
    return (
      <section className="panel p-6 text-center">
        <p className="text-sm muted">
          No activities yet. Upload a TCX or GPX file to get started.
        </p>
      </section>
    )
  }

  const from = offset + 1
  const to = Math.min(offset + workouts.length, total)

  return (
    <section
      className="panel"
      aria-labelledby="workouts-heading"
    >
      <div className="flex items-baseline justify-between p-4">
        <h2 id="workouts-heading" className="text-sm font-semibold">
          Activities
        </h2>
        <p className="text-xs muted">
          {from}–{to} of {total}
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="muted border-y border-[var(--border)] text-left text-xs uppercase tracking-wide">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">Date</th>
              <th scope="col" className="px-4 py-2 font-medium">Activity</th>
              <th scope="col" className="px-4 py-2 font-medium">Sport</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Distance</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Time</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Pace</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Climb</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">HR</th>
              <th scope="col" className="px-4 py-2"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {workouts.map((workout) => (
              <tr key={workout.id} className="hover:bg-[var(--surface-sunken)]">
                <td className="whitespace-nowrap px-4 py-2 tabular-nums">
                  {formatDate(workout.start_time)}
                  <span className="ml-1 text-xs muted">
                    {formatLocalTime(workout.start_time, workout.utc_offset_minutes)}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <button
                    type="button"
                    onClick={() => onOpen(workout)}
                    className="text-left font-medium text-sky-700 hover:underline dark:text-sky-400"
                  >
                    {workout.name}
                  </button>
                </td>
                <td className="whitespace-nowrap px-4 py-2">
                  <span
                    aria-hidden="true"
                    className="mr-2 inline-block h-2 w-2 rounded-full align-middle"
                    style={{ backgroundColor: sportColor(workout.sport_type, dark) }}
                  />
                  {sportLabel(workout.sport_type)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {formatDistance(workout.total_distance)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {formatDuration(workout.total_time)}
                </td>
                <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums">
                  {formatPaceOrSpeed(workout.sport_type, workout.total_distance, workout.total_time)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {formatElevation(workout.total_elevation_gain)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {formatHeartRate(workout.avg_heart_rate)}
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => onDelete(workout)}
                    aria-label={`Delete ${workout.name}`}
                    className="muted text-xs hover:text-red-700 dark:hover:text-red-400"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > limit && (
        <div className="flex items-center justify-between p-4">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => onPage(Math.max(0, offset - limit))}
            className="rounded-md border border-[var(--border)] px-3 py-1 text-sm disabled:opacity-40"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={offset + limit >= total}
            onClick={() => onPage(offset + limit)}
            className="rounded-md border border-[var(--border)] px-3 py-1 text-sm disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </section>
  )
}
