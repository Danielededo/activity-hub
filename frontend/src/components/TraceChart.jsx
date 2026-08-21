import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CHART_INK, SINGLE_SERIES } from '../theme'
import { useColorScheme } from '../hooks/useColorScheme'
import { formatElapsed } from '../utils/formatters'

/**
 * One measure over the course of an activity.
 *
 * Heart rate and elevation get a chart each rather than sharing a frame on two
 * y-scales: with two scales, where the lines cross is decided by the axis
 * ranges, not by the ride, and readers take the crossing to mean something.
 */
export default function TraceChart({ title, unit, samples, dataKey, formatValue, xFormatter }) {
  const dark = useColorScheme()
  const ink = CHART_INK[dark ? 'dark' : 'light']
  const colour = dark ? SINGLE_SERIES.dark : SINGLE_SERIES.light

  const points = (samples ?? []).filter((sample) => sample[dataKey] != null)
  if (points.length < 2) return null

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide muted">
        {title}
      </h3>
      <div className="mt-2 h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid vertical={false} stroke={ink.grid} />
            <XAxis
              dataKey="elapsed"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={xFormatter ?? formatElapsed}
              tick={{ fill: ink.axis, fontSize: 11 }}
              stroke={ink.grid}
              // Without a gap the last tick collides with the one before it.
              minTickGap={48}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={['auto', 'auto']}
              tick={{ fill: ink.axis, fontSize: 11 }}
              stroke={ink.grid}
              width={44}
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
              labelFormatter={(x) => `At ${(xFormatter ?? formatElapsed)(x)}`}
              formatter={(value) => [formatValue ? formatValue(value) : `${value} ${unit}`, title]}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={colour}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
