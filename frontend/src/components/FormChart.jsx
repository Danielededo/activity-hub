import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CHART_INK, seriesColors } from '../theme'
import { useColorScheme } from '../hooks/useColorScheme'
import { formatDate, formatMonth, formatSigned, formatWeek } from '../utils/formatters'

/** The three series, in the palette's fixed slot order. */
const SERIES = [
  { key: 'fitness', label: 'Fitness', hint: '42-day average' },
  { key: 'fatigue', label: 'Fatigue', hint: '7-day average' },
  { key: 'form', label: 'Form', hint: 'fitness − fatigue' },
]

const RANGES = [
  { days: 90, label: '90 days' },
  { days: 180, label: '6 months' },
  { days: 365, label: '1 year' },
]

/** Above this many days the ticks carry the year. */
const YEARLESS_DAYS = 180

/**
 * What training has built, what it has cost, and what is left over.
 *
 * All three are the same measure in the same unit — Edwards' TRIMP, the figure
 * the zone panel reports — so they share one axis. The usual version of this
 * chart puts form on a second y-scale, which makes the point where the lines
 * cross an artefact of the two ranges rather than anything that happened.
 */
export default function FormChart({ summary, days, onDaysChange }) {
  const dark = useColorScheme()
  const ink = CHART_INK[dark ? 'dark' : 'light']
  const colours = seriesColors(SERIES.length, dark)

  if (!summary?.series?.length) {
    return (
      <section className="panel p-6 text-center" aria-labelledby="form-heading">
        <h2 id="form-heading" className="sr-only">
          Fitness and fatigue
        </h2>
        <p className="text-sm muted">
          {summary?.max_heart_rate == null
            ? 'No heart rate recorded yet, so there is no training load to average.'
            : 'No training load yet.'}
        </p>
      </section>
    )
  }

  // The last day of the window is today, and today is what "how am I now"
  // means. Everything before it is how it got there.
  const latest = summary.series[summary.series.length - 1]
  const coldStart = summary.warmup_days === 0

  return (
    <section className="panel p-4" aria-labelledby="form-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="form-heading" className="text-sm font-semibold">
          Fitness and fatigue
        </h2>
        <label className="text-xs muted">
          Range{' '}
          <select
            className="rounded-md border border-[var(--border)] bg-transparent px-1 py-0.5 text-xs"
            value={days}
            onChange={(event) => onDaysChange(Number(event.target.value))}
          >
            {RANGES.map((range) => (
              <option key={range.days} value={range.days}>
                {range.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Today's three figures, which double as the legend: identity is never
          colour alone, and a reader wanting "where am I now" does not have to
          read it off the right-hand end of a line.

          Grouped left rather than spread across the panel. On a wide screen a
          three-column grid put the third figure a third of a metre from the
          first, and three numbers that far apart read as three unrelated
          columns instead of as one legend. */}
      <dl className="mt-3 flex flex-wrap gap-x-10 gap-y-3">
        {SERIES.map((series, index) => (
          <div key={series.key}>
            <dt className="flex items-center gap-1.5 text-xs uppercase tracking-wide muted">
              <span
                aria-hidden="true"
                className="inline-block h-2 w-2 shrink-0 rounded-full"
                style={{ background: colours[index] }}
              />
              {series.label}
            </dt>
            <dd className="text-lg">
              {series.key === 'form' ? formatSigned(latest.form) : Math.round(latest[series.key])}
            </dd>
            <dd className="text-xs muted">{series.hint}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={summary.series} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={ink.grid} />
            {/* Form's baseline. Solid, like every other rule here: a dashed one
                reads as a projection or a threshold rather than as zero. */}
            <ReferenceLine y={0} stroke={ink.axis} strokeWidth={1} />
            <XAxis
              dataKey="day"
              // A year of days ran "Aug 22" to "Aug 21" without it: two labels
              // a year apart that read as the same fortnight.
              tickFormatter={days > YEARLESS_DAYS ? formatMonth : formatWeek}
              tick={{ fill: ink.axis, fontSize: 11 }}
              stroke={ink.grid}
              minTickGap={40}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: ink.axis, fontSize: 11 }}
              stroke={ink.grid}
              // Room for a three-digit load and a minus sign. An axis narrower
              // than its own labels drops the leading character and reads as a
              // different number.
              width={44}
              tickFormatter={(value) => String(Math.round(value))}
            />
            <Tooltip
              cursor={{ stroke: ink.axis, strokeWidth: 1 }}
              contentStyle={{
                background: ink.tooltipBg,
                borderColor: ink.grid,
                color: ink.tooltipInk,
                fontSize: 12,
                borderRadius: 6,
              }}
              // The dot beside a value carries identity; the value itself
              // wears text ink. Recharts colours the text with the series hue
              // by default, which puts a 2.7:1 green — and a 2.0:1 pale blue —
              // on a white tooltip: the one place the palette's contrast
              // warning actually bites.
              itemStyle={{ color: ink.tooltipInk }}
              labelFormatter={formatDate}
              // Declaration order, not by value. Recharts sorts by name, so the
              // tooltip listed fatigue, fitness, form while the figures above
              // it read fitness, fatigue, form — the same three numbers in two
              // orders, one of which the reader has to re-scan every hover.
              itemSorter={(item) => SERIES.findIndex((series) => series.key === item.dataKey)}
              formatter={(value, key) => [
                key === 'form' ? formatSigned(value) : Math.round(value),
                SERIES.find((series) => series.key === key)?.label ?? key,
              ]}
            />
            {SERIES.map((series, index) => (
              <Line
                key={series.key}
                dataKey={series.key}
                name={series.label}
                stroke={colours[index]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: ink.surface }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-1 text-xs muted">
        {/* Kept on one line each: a line break inside "yesterday&rsquo;s" put a
            space in front of the apostrophe on the rendered page. */}
        Exponential averages of daily load: 42 days for fitness, 7 for fatigue.{' '}
        Form is <em>yesterday&rsquo;s</em> difference, so it reads as freshness before a session
        rather than after it.
        {coldStart && (
          <>
            {' '}
            The first weeks climb out of zero because there is no history behind them, not because
            fitness was built then.
          </>
        )}
        {summary.untracked_activities > 0 && (
          <>
            {' '}
            {summary.untracked_activities}{' '}
            {summary.untracked_activities === 1 ? 'activity' : 'activities'} in this window recorded
            no heart rate. They earn no load, so they read here as rest days.
          </>
        )}
      </p>
    </section>
  )
}
