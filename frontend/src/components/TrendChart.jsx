import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CHART_INK, SINGLE_SERIES } from '../theme'
import { useColorScheme } from '../hooks/useColorScheme'
import { formatDistance, formatDuration, formatWeek } from '../utils/formatters'

/**
 * Distance per week.
 *
 * Bars, not a line: the weeks are discrete buckets and a line between them
 * would imply a continuous quantity that was never measured. Quiet weeks are
 * real zeroes, which is exactly what a gap in a bar chart says.
 *
 * One measure on the axis. Activity count and time live in the tooltip rather
 * than on a second y-scale — two scales in one frame make any comparison
 * between them an artefact of where the axes were put.
 */
function ChartTooltip({ active, payload, dark }) {
  if (!active || !payload?.length) return null
  const week = payload[0].payload
  const ink = CHART_INK[dark ? 'dark' : 'light']

  return (
    <div
      className="rounded-md border px-3 py-2 text-xs shadow-sm"
      style={{ background: ink.tooltipBg, color: ink.tooltipInk, borderColor: ink.grid }}
    >
      <p className="font-semibold">Week of {formatWeek(week.week_start)}</p>
      <p className="mt-1 tabular-nums">{formatDistance(week.total_distance)}</p>
      <p className="tabular-nums">{formatDuration(week.total_time)}</p>
      <p className="tabular-nums">
        {week.workout_count} {week.workout_count === 1 ? 'activity' : 'activities'}
      </p>
    </div>
  )
}

export default function TrendChart({ buckets, weeks, onWeeksChange }) {
  const dark = useColorScheme()
  const ink = CHART_INK[dark ? 'dark' : 'light']
  const colour = dark ? SINGLE_SERIES.dark : SINGLE_SERIES.light

  return (
    <section
      className="panel p-4"
      aria-labelledby="trend-heading"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="trend-heading" className="text-sm font-semibold">
          Weekly distance
        </h2>
        <label className="text-xs muted">
          <span className="mr-2">Range</span>
          <select
            value={weeks}
            onChange={(event) => onWeeksChange(Number(event.target.value))}
            className="rounded-md border border-[var(--border)] bg-[var(--surface-sunken)] px-2 py-1"
          >
            <option value={8}>8 weeks</option>
            <option value={12}>12 weeks</option>
            <option value={26}>26 weeks</option>
            <option value={52}>52 weeks</option>
          </select>
        </label>
      </div>

      <div className="mt-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={buckets ?? []} margin={{ top: 4, right: 4, bottom: 0, left: -8 }}>
            <CartesianGrid vertical={false} stroke={ink.grid} />
            <XAxis
              dataKey="week_start"
              tickFormatter={formatWeek}
              tick={{ fill: ink.axis, fontSize: 11 }}
              stroke={ink.grid}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={(metres) => (metres / 1000).toFixed(0)}
              tick={{ fill: ink.axis, fontSize: 11 }}
              stroke={ink.grid}
              width={40}
              label={{
                value: 'km',
                position: 'insideTopLeft',
                fill: ink.axis,
                fontSize: 11,
                offset: 8,
              }}
            />
            <Tooltip
              content={<ChartTooltip dark={dark} />}
              cursor={{ fill: ink.grid, fillOpacity: 0.35 }}
            />
            <Bar dataKey="total_distance" fill={colour} radius={[4, 4, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
