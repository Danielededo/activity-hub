import { formatDistance, formatDuration, formatElevation } from '../utils/formatters'

/**
 * Training by calendar year, most recent first.
 *
 * Local years, not UTC ones: a ride at half eleven on New Year's Eve belongs
 * to the year it felt like, which is what the API decides before sending it.
 */
export default function YearlyTotals({ years }) {
  if (!years?.length) {
    return (
      <section className="panel p-6 text-center" aria-labelledby="yearly-heading">
        <h2 id="yearly-heading" className="sr-only">
          By year
        </h2>
        <p className="text-sm muted">Nothing recorded yet.</p>
      </section>
    )
  }

  return (
    <section className="panel p-4" aria-labelledby="yearly-heading">
      <h2 id="yearly-heading" className="text-sm font-semibold">
        By year
      </h2>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="muted border-y border-[var(--border)] text-left text-xs uppercase tracking-wide">
            <tr>
              <th scope="col" className="py-1 pr-3 font-medium">Year</th>
              <th scope="col" className="py-1 pr-3 text-right font-medium">Activities</th>
              <th scope="col" className="py-1 pr-3 text-right font-medium">Distance</th>
              <th scope="col" className="py-1 pr-3 text-right font-medium">Time</th>
              <th scope="col" className="py-1 text-right font-medium">Climb</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {years.map((year) => (
              <tr key={year.year}>
                <th scope="row" className="py-1 pr-3 text-left font-medium tabular-nums">
                  {year.year}
                </th>
                <td className="py-1 pr-3 text-right tabular-nums">{year.workout_count}</td>
                <td className="py-1 pr-3 text-right tabular-nums">
                  {formatDistance(year.total_distance)}
                </td>
                <td className="py-1 pr-3 text-right tabular-nums">
                  {formatDuration(year.total_time)}
                </td>
                <td className="py-1 text-right tabular-nums">
                  {formatElevation(year.total_elevation_gain)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
