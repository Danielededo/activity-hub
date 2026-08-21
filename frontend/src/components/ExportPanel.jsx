import { exportUrl } from '../api/client'
import { hasFilters } from './FilterBar'

/**
 * Getting your data out, as links rather than buttons.
 *
 * A link lets the browser do the download — streamed straight to disk, with the
 * filename the server chose, and a progress indicator for a library big enough
 * to need one. Fetching the bytes into JavaScript first would buy nothing and
 * would fall over on exactly the export that matters.
 */
export default function ExportPanel({ userId, filters, total }) {
  const filtered = hasFilters(filters)
  const query = { userId, ...filters }

  return (
    <section className="panel p-4" aria-labelledby="export-heading">
      <h2 id="export-heading" className="text-sm font-semibold">
        Export
      </h2>
      <p className="mt-1 text-xs muted">
        {filtered
          ? // Saying which it is matters: downloading a filtered export and
            // finding it short is worse than being told up front.
            `The ${total} ${total === 1 ? 'activity' : 'activities'} matching the filters above.`
          : 'Everything you have uploaded.'}
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <a
          className="rounded-md border border-[var(--border)] px-3 py-1 text-sm"
          href={exportUrl('/export/activities.csv', query)}
        >
          Summary as CSV
        </a>
        <a
          className="rounded-md border border-[var(--border)] px-3 py-1 text-sm"
          href={exportUrl('/export/activities.zip', query)}
        >
          {/* "Tracks", not "all activities": the line above already says how
              many, and the two contradicted each other under a filter. */}
          Tracks as GPX
        </a>
      </div>

      <p className="mt-2 text-xs muted">
        The CSV carries the figures for each activity; the GPX files carry the samples
        behind them. GPX has nowhere to put a device&rsquo;s own totals, so the two
        together are the complete picture.
      </p>
    </section>
  )
}
