import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CHART_INK, ORDINAL_RAMP } from '../theme'
import { useColorScheme } from '../hooks/useColorScheme'
import { formatDuration, formatShortDuration, formatWeek } from '../utils/formatters'
import { zoneRange, zoneShares, zonedSeconds } from '../utils/zones'

/**
 * How much time goes into each heart-rate zone, lifetime and week by week.
 *
 * The weekly chart carries time, and the training load rides in its tooltip
 * rather than on a second axis. Two measures on two y-scales would make the
 * point where they cross an artefact of the axis ranges, and readers take a
 * crossing to mean something.
 */
export default function HeartRateZones({ summary, weeks, onWeeksChange }) {
  const dark = useColorScheme()
  const ramp = dark ? ORDINAL_RAMP.dark : ORDINAL_RAMP.light
  const ink = CHART_INK[dark ? 'dark' : 'light']

  if (!summary?.zones?.length) {
    return (
      <section className="panel p-6 text-center" aria-labelledby="zones-heading">
        <h2 id="zones-heading" className="sr-only">
          Heart-rate zones
        </h2>
        <p className="text-sm muted">
          {summary?.max_heart_rate == null
            ? 'No heart rate recorded yet, so there are no zones to show.'
            : 'No time in zone yet.'}
        </p>
      </section>
    )
  }

  const bands = zoneShares(summary.zones)
  const total = zonedSeconds(summary.zones)
  const byZone = new Map(summary.zones.map((band) => [band.zone, band]))

  const buckets = (summary.weekly ?? []).map((week) => {
    const row = { week: week.week_start, load: week.load }
    for (const entry of week.seconds) row[`z${entry.zone}`] = entry.seconds / 60
    return row
  })

  return (
    <section className="panel p-4" aria-labelledby="zones-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="zones-heading" className="text-sm font-semibold">
          Heart-rate zones
        </h2>
        <p className="text-xs muted">
          {/* Where the maximum came from, because an observed one is a floor:
              a peak nobody has pushed to reads low and lifts every zone. */}
          max {summary.max_heart_rate} bpm ({summary.max_heart_rate_source}) · load{' '}
          <span className="tabular-nums">{Math.round(summary.total_load)}</span>
        </p>
      </div>

      <dl className="mt-4 space-y-2">
        {bands.map((band) => (
          <div key={band.zone} className="grid grid-cols-[7rem_1fr_4.5rem] items-center gap-2">
            <dt className="flex items-center gap-2 text-xs">
              <span
                aria-hidden="true"
                className="inline-block h-2 w-2 shrink-0 rounded-full"
                style={{ background: ramp[band.zone - 1] }}
              />
              <span className="truncate">
                Z{band.zone} {band.name}
              </span>
            </dt>
            <dd className="flex items-center gap-2">
              <span className="h-2 flex-1 rounded-sm bg-[var(--surface-sunken)]">
                <span
                  className="block h-2 rounded-sm"
                  style={{ width: `${band.share * 100}%`, background: ramp[band.zone - 1] }}
                />
              </span>
              <span className="shrink-0 text-xs muted">{zoneRange(band)}</span>
            </dd>
            <dd className="text-right text-xs tabular-nums">{formatDuration(band.seconds)}</dd>
          </div>
        ))}
      </dl>

      {summary.seconds_below_zones > 0 && (
        <p className="mt-2 text-xs muted">
          {/* Reported rather than folded into zone one, which is the zone people
              read as "my easy work". */}
          plus {formatDuration(summary.seconds_below_zones)} below Z{bands[0].zone}, warming up or
          standing still
        </p>
      )}

      <div className="mt-5 flex items-baseline justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide muted">By week</h3>
        <label className="text-xs muted">
          Range{' '}
          <select
            className="rounded-md border border-[var(--border)] bg-transparent px-1 py-0.5 text-xs"
            value={weeks}
            onChange={(event) => onWeeksChange(Number(event.target.value))}
          >
            {[8, 12, 26, 52].map((option) => (
              <option key={option} value={option}>
                {option} weeks
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-2 h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={buckets} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={ink.grid} />
            <XAxis
              dataKey="week"
              tickFormatter={formatWeek}
              tick={{ fill: ink.axis, fontSize: 11 }}
              stroke={ink.grid}
              minTickGap={24}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: ink.axis, fontSize: 11 }}
              stroke={ink.grid}
              // Wide enough for the longest label this formatter produces,
              // with a left margin of zero rather than the negative one that
              // gains a few pixels of plot. At 44 with a bare "m" unit the axis
              // clipped its leading digit and read 110 minutes as "10m"; an
              // axis that lies is worse than no axis.
              width={58}
              tickFormatter={(minutes) => formatShortDuration(minutes * 60)}
            />
            <Tooltip
              cursor={{ fill: ink.grid, fillOpacity: 0.3 }}
              contentStyle={{
                background: ink.tooltipBg,
                borderColor: ink.grid,
                color: ink.tooltipInk,
                fontSize: 12,
                borderRadius: 6,
              }}
              labelFormatter={(week) => `Week of ${formatWeek(week)}`}
              formatter={(minutes, key) => {
                const zone = Number(String(key).slice(1))
                const band = byZone.get(zone)
                return [formatDuration(minutes * 60), `Z${zone} ${band?.name ?? ''}`]
              }}
            />
            {/* Stacked in zone order, so the bar reads bottom-up from easy to
                hard the same way the list above reads top-down. */}
            {bands.map((band) => (
              <Bar
                key={band.zone}
                dataKey={`z${band.zone}`}
                stackId="zones"
                fill={ramp[band.zone - 1]}
                name={`Z${band.zone}`}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-1 text-xs muted">
        {formatDuration(total)} in zone across your history. Load is Edwards&rsquo; TRIMP: minutes
        in a zone counted once for Z1 and five times for Z5.
      </p>
    </section>
  )
}
