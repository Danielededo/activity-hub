import { Suspense, lazy, useCallback, useEffect, useState } from 'react'
import {
  deleteWorkout,
  errorMessage,
  fetchAnalysis,
  fetchRecords,
  fetchWeekly,
  fetchWorkout,
  fetchWorkouts,
} from '../api/client'
import FilterBar, { EMPTY_FILTERS, hasFilters } from './FilterBar'
import Records from './Records'
import SportBreakdown from './SportBreakdown'
import StatsCards from './StatsCards'
import TrendChart from './TrendChart'
import UploadForm from './UploadForm'
import WorkoutTable from './WorkoutTable'
import YearlyTotals from './YearlyTotals'

// Split out: the route map and the per-activity traces are only needed once
// somebody opens an activity, so they stay out of the first paint.
const WorkoutDetail = lazy(() => import('./WorkoutDetail'))

const PAGE_SIZE = 20

export default function Dashboard({ profile }) {
  const userId = profile.id
  const [summary, setSummary] = useState(null)
  const [weekly, setWeekly] = useState(null)
  const [records, setRecords] = useState(null)
  const [weeks, setWeeks] = useState(12)
  const [page, setPage] = useState({ items: [], total: 0, offset: 0 })
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(null)

  // Loading is split from applying it, so the effects below set state in a
  // promise callback rather than in their own body. Totals and the list are
  // also split from each other: the lifetime figures, the trend and the
  // records do not depend on the filters, so narrowing the list must not
  // re-request them.
  const loadTotals = useCallback(
    () => Promise.all([fetchAnalysis(userId), fetchWeekly(userId, weeks), fetchRecords(userId)]),
    [userId, weeks],
  )

  const loadList = useCallback(
    () => fetchWorkouts({ userId, limit: PAGE_SIZE, offset, ...filters }),
    [userId, offset, filters],
  )

  const applyTotals = useCallback(([analysis, trend, bests]) => {
    setSummary(analysis)
    setWeekly(trend)
    setRecords(bests)
    setError(null)
  }, [])

  const applyList = useCallback((workouts) => {
    setPage({ items: workouts.items, total: workouts.total, offset: workouts.offset })
    setError(null)
  }, [])

  const fail = useCallback((caught, fallback) => setError(errorMessage(caught, fallback)), [])

  useEffect(() => {
    let cancelled = false
    loadTotals()
      .then((data) => {
        if (!cancelled) applyTotals(data)
      })
      .catch((caught) => {
        if (!cancelled) fail(caught, 'Could not load your training')
      })
    return () => {
      cancelled = true
    }
  }, [loadTotals, applyTotals, fail])

  useEffect(() => {
    let cancelled = false
    loadList()
      .then((data) => {
        if (!cancelled) applyList(data)
      })
      .catch((caught) => {
        if (!cancelled) fail(caught, 'Could not load your activities')
      })
    return () => {
      cancelled = true
    }
  }, [loadList, applyList, fail])

  function reload() {
    loadTotals()
      .then(applyTotals)
      .catch((caught) => fail(caught, 'Could not load your training'))
    loadList()
      .then(applyList)
      .catch((caught) => fail(caught, 'Could not load your activities'))
  }

  function changeFilters(next) {
    // Back to the first page: page three of the whole library is not page
    // three of a filtered one, and landing past the end shows nothing.
    setOffset(0)
    setFilters(next)
  }

  // A record names an activity but does not carry it, so opening one from
  // there means fetching it first.
  function openById(workoutId) {
    fetchWorkout(workoutId, userId)
      .then(setSelected)
      .catch((caught) => fail(caught, 'Could not open that activity'))
  }

  async function remove(workout) {
    try {
      await deleteWorkout(workout.id, userId)
      if (selected?.id === workout.id) setSelected(null)
      reload()
    } catch (caught) {
      fail(caught, 'Could not delete the activity')
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Activity Hub</h1>
          <p className="text-sm muted">{profile.full_name}</p>
        </div>
      </header>

      {error && (
        <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="mt-6 space-y-6">
        <StatsCards summary={summary} />

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <TrendChart buckets={weekly?.buckets} weeks={weeks} onWeeksChange={setWeeks} />
          </div>
          <SportBreakdown bySport={summary?.by_sport} />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Records bySport={records?.by_sport} onOpenWorkout={openById} />
          </div>
          <YearlyTotals years={records?.yearly} />
        </div>

        <UploadForm userId={userId} onUploaded={reload} />

        {selected && (
          <Suspense
            fallback={
              <p className="text-sm muted" role="status">
                Loading the activity…
              </p>
            }
          >
            <WorkoutDetail
              key={selected.id}
              workout={selected}
              userId={userId}
              onClose={() => setSelected(null)}
            />
          </Suspense>
        )}

        <FilterBar
          // The sports somebody has actually recorded, so the list never offers
          // a filter that can only come back empty. Deliberately the unfiltered
          // breakdown: the options should not vanish as you narrow things down.
          sports={summary?.by_sport ?? []}
          filters={filters}
          onChange={changeFilters}
        />

        <WorkoutTable
          workouts={page.items}
          total={page.total}
          limit={PAGE_SIZE}
          offset={page.offset}
          onPage={setOffset}
          onOpen={setSelected}
          onDelete={remove}
          filtered={hasFilters(filters)}
        />
      </div>
    </div>
  )
}
