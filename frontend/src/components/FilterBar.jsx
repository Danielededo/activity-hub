import { useEffect, useState } from 'react'
import { sportLabel } from '../utils/formatters'

/** No filter set. Also what the Clear button restores. */
export const EMPTY_FILTERS = { sportType: '', dateFrom: '', dateTo: '', q: '' }

/** Typing "Monte" would otherwise be five requests, four of them stale. */
const SEARCH_DEBOUNCE_MS = 300

export function hasFilters(filters) {
  return Object.values(filters).some((value) => value !== '')
}

/**
 * Narrows the activity list by sport, date range and name.
 *
 * Lives outside the table on purpose: the table replaces itself with an empty
 * state when nothing matches, and a filter bar inside it would disappear
 * exactly when it is needed to undo the filter.
 */
export default function FilterBar({ sports, filters, onChange, disabled = false }) {
  // The text input keeps its own value so every keystroke does not become a
  // request. Everything else is applied the moment it changes: picking a sport
  // is a decision, typing is not yet one.
  const [term, setTerm] = useState(filters.q)

  useEffect(() => {
    if (term === filters.q) return undefined
    const timer = setTimeout(() => onChange({ ...filters, q: term }), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [term, filters, onChange])

  function set(key, value) {
    onChange({ ...filters, [key]: value })
  }

  function clear() {
    setTerm('')
    onChange(EMPTY_FILTERS)
  }

  const field = 'mt-1 w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-sm'
  const label = 'text-xs font-medium uppercase tracking-wide muted'

  return (
    <section className="panel p-4" role="search" aria-label="Filter activities">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className={label} htmlFor="filter-sport">
            Sport
          </label>
          <select
            id="filter-sport"
            className={field}
            value={filters.sportType}
            disabled={disabled}
            onChange={(event) => set('sportType', event.target.value)}
          >
            <option value="">All sports</option>
            {sports.map((sport) => (
              <option key={sport.sport_type} value={sport.sport_type}>
                {sportLabel(sport.sport_type)} ({sport.workout_count})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className={label} htmlFor="filter-from">
            From
          </label>
          <input
            id="filter-from"
            type="date"
            className={field}
            value={filters.dateFrom}
            disabled={disabled}
            // A hint to the picker, not a guarantee: a typed-in date can still
            // be out of range, so the server refuses a reversed range too.
            max={filters.dateTo || undefined}
            onChange={(event) => set('dateFrom', event.target.value)}
          />
        </div>

        <div>
          <label className={label} htmlFor="filter-to">
            To
          </label>
          <input
            id="filter-to"
            type="date"
            className={field}
            value={filters.dateTo}
            disabled={disabled}
            min={filters.dateFrom || undefined}
            onChange={(event) => set('dateTo', event.target.value)}
          />
        </div>

        <div>
          <label className={label} htmlFor="filter-name">
            Name contains
          </label>
          <input
            id="filter-name"
            type="search"
            className={field}
            placeholder="Morning ride"
            value={term}
            disabled={disabled}
            onChange={(event) => setTerm(event.target.value)}
          />
        </div>
      </div>

      {hasFilters(filters) && (
        <button
          type="button"
          onClick={clear}
          className="mt-3 rounded-md border border-[var(--border)] px-3 py-1 text-sm"
        >
          Clear filters
        </button>
      )}
    </section>
  )
}
