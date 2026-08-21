import { ORDINAL_RAMP } from '../theme'
import { useColorScheme } from '../hooks/useColorScheme'
import { formatDuration } from '../utils/formatters'
import { zoneRange, zoneShares, zonedSeconds } from '../utils/zones'

/**
 * One activity's time in zone, as a single bar.
 *
 * A bar rather than five: the question here is the shape of one session — how
 * much of it was easy and how much was hard — and that reads off proportions
 * side by side. The dashboard's panel breaks the same data out per zone,
 * because there the question is how much of each you do.
 */
export default function ZoneBar({ zones, load }) {
  const dark = useColorScheme()
  const ramp = dark ? ORDINAL_RAMP.dark : ORDINAL_RAMP.light
  const total = zonedSeconds(zones)

  if (!total) return null

  const bands = zoneShares(zones)

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide muted">Time in zone</h3>
        {load > 0 && (
          <p className="text-xs muted">
            load <span className="tabular-nums">{Math.round(load)}</span>
          </p>
        )}
      </div>

      {/* gap-0.5 is the surface showing through: touching segments are told
          apart by the gap, not by a stroke drawn around each one. */}
      <div className="mt-2 flex h-3 gap-0.5 overflow-hidden rounded-sm">
        {bands.map((band) => (
          <div
            key={band.zone}
            style={{ width: `${band.share * 100}%`, background: ramp[band.zone - 1] }}
            title={`Z${band.zone} ${band.name} · ${zoneRange(band)} · ${formatDuration(band.seconds)}`}
          />
        ))}
      </div>

      {/* Named in text, never by colour alone. Only the zones that carry time,
          so a session that never left endurance does not list four blanks. */}
      <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {bands
          .filter((band) => band.seconds > 0)
          .map((band) => (
            <div key={band.zone} className="flex items-center gap-1">
              <span
                aria-hidden="true"
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: ramp[band.zone - 1] }}
              />
              <dt className="muted">
                Z{band.zone} {band.name}
              </dt>
              <dd className="tabular-nums">{formatDuration(band.seconds)}</dd>
            </div>
          ))}
      </dl>
    </div>
  )
}
