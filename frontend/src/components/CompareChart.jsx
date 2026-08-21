import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CHART_INK, seriesColors } from '../theme'
import { useColorScheme } from '../hooks/useColorScheme'
import { formatDistance } from '../utils/formatters'
import { sharedGrid } from '../utils/track'

/**
 * One measure from two activities, against distance travelled.
 *
 * Distance, not elapsed time: run the same route a minute slower and a time
 * axis pulls the two apart from the first hill, while a distance axis keeps the
 * hill in the same place — which is the whole point of putting them together.
 *
 * One y axis, as everywhere else here. Two measures of different scale on two
 * scales make the point where the lines cross an artefact of the axis ranges,
 * and readers take a crossing to mean something.
 */
export default function CompareChart({ title, unit, series, dataKey, formatValue, formatAxis }) {
  const dark = useColorScheme()
  const ink = CHART_INK[dark ? 'dark' : 'light']
  const colours = seriesColors(2, dark)

  const drawable = series.filter((entry) => entry.points.some((p) => p[dataKey] != null))
  if (drawable.length < 2) return null

  // Resampled onto one grid rather than merged on each track's own samples: see
  // sharedGrid for why merging shatters both lines exactly where they overlap.
  const data = sharedGrid(drawable, dataKey)

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h4 className="text-xs font-semibold uppercase tracking-wide muted">
          {title}
          {unit && <span className="ml-1 font-normal normal-case">({unit})</span>}
        </h4>
        {/* Written as HTML rather than handed to the chart library: a legend is
            the dependable half of identity, and it should not depend on the
            chart having managed to lay itself out. */}
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {drawable.map((entry, index) => (
            <li key={entry.id} className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="inline-block h-2 w-2 shrink-0 rounded-full"
                style={{ background: colours[index] }}
              />
              {entry.name}
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-2 h-44">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={ink.grid} />
            <XAxis
              dataKey="distance"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={formatDistance}
              tick={{ fill: ink.axis, fontSize: 11 }}
              stroke={ink.grid}
              minTickGap={40}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={['auto', 'auto']}
              tick={{ fill: ink.axis, fontSize: 11 }}
              stroke={ink.grid}
              // The unit lives in the heading, so the axis carries bare
              // numbers. With the unit on every tick the labels outgrew the
              // axis and were clipped — "28.8 km/h" arriving as "8.8 km/h".
              width={44}
              tickFormatter={formatAxis ?? formatValue}
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
              labelFormatter={(metres) => `At ${formatDistance(metres)}`}
              formatter={(value, key) => [
                formatValue(value),
                drawable[Number(String(key).slice(1))].name,
              ]}
            />
            {drawable.map((entry, index) => (
              <Line
                key={entry.id}
                dataKey={`v${index}`}
                name={entry.name}
                stroke={colours[index]}
                strokeWidth={2}
                dot={false}
                // A gap in one activity must not join across; the other keeps
                // its own line.
                connectNulls={false}
                activeDot={{ r: 4, strokeWidth: 2 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
