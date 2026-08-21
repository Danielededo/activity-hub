import { useMemo, useState } from 'react'
import { CHART_INK, SINGLE_SERIES, ORDINAL_RAMP } from '../theme'
import { useColorScheme } from '../hooks/useColorScheme'
import { haversineDistance } from '../utils/geo'
import { formatDistance, formatElapsed, formatRate } from '../utils/formatters'

// The drawing box, and the viewBox padded around it to fit the stroke width.
const BOX = 100
const VIEW_MIN = -4
const VIEW_SIZE = 108

/**
 * Above this a "speed" is a GPS artefact, not movement (m/s, ≈ 120 km/h).
 *
 * Deliberately a speed and not a distance: the samples arrive downsampled, so
 * consecutive ones can be hundreds of metres apart quite legitimately, and a
 * distance ceiling would throw away real riding at a high stride.
 */
const IMPLAUSIBLE_SPEED_MS = 120_000 / 3_600

/** Project located samples into the box, north up and undistorted. */
function project(samples) {
  const located = (samples ?? []).filter(
    (sample) => sample.latitude != null && sample.longitude != null,
  )
  if (located.length < 2) return null

  const lats = located.map((sample) => sample.latitude)
  const lons = located.map((sample) => sample.longitude)
  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)
  const minLon = Math.min(...lons)
  const maxLon = Math.max(...lons)

  // Longitude degrees are shorter than latitude ones away from the equator,
  // so scale them by cos(latitude) or the route comes out stretched.
  const midLat = ((minLat + maxLat) / 2) * (Math.PI / 180)
  const spanX = Math.max((maxLon - minLon) * Math.cos(midLat), 1e-6)
  const spanY = Math.max(maxLat - minLat, 1e-6)
  const scale = Math.min(BOX / spanX, BOX / spanY)
  const offsetX = (BOX - spanX * scale) / 2
  const offsetY = (BOX - spanY * scale) / 2

  return located.map((sample) => ({
    sample,
    x: offsetX + (sample.longitude - minLon) * Math.cos(midLat) * scale,
    // SVG y grows downwards; north should be up.
    y: offsetY + (maxLat - sample.latitude) * scale,
  }))
}

/**
 * Metres and seconds along the track, and the speed of each hop.
 *
 * There is one fewer speed than there are points: `speeds[i]` belongs to the
 * hop arriving at point i + 1.
 */
function measure(points) {
  const distances = [0]
  const elapsed = [0]
  const speeds = []
  const first = points[0].sample.timestamp
  const start = first ? new Date(first).getTime() : null

  for (let index = 1; index < points.length; index += 1) {
    const from = points[index - 1].sample
    const to = points[index].sample
    const metres = haversineDistance(from.latitude, from.longitude, to.latitude, to.longitude)
    distances.push(distances[index - 1] + metres)

    if (start == null || !to.timestamp) {
      elapsed.push(elapsed[index - 1])
      speeds.push(null)
      continue
    }
    elapsed.push((new Date(to.timestamp).getTime() - start) / 1000)
    const seconds = elapsed[index] - elapsed[index - 1]
    const speed = seconds > 0 ? metres / seconds : null
    speeds.push(speed != null && speed <= IMPLAUSIBLE_SPEED_MS ? speed : null)
  }

  return { distances, elapsed, speeds }
}

/**
 * Four cut points splitting the segments into five equally populated bands,
 * with the extremes the legend has to name.
 *
 * Quantiles of this activity rather than fixed thresholds: the question the
 * colour answers is "where was I fast *on this ride*", and absolute bands would
 * paint a whole hike in one step. The legend carries the real figures, so the
 * colours can still be read in absolute terms.
 *
 * The extremes are the slowest and fastest stretch, not the outer cut points.
 * Labelling the ends of a ramp with its 20th and 80th percentile understates
 * the range it covers, and on a steady ride prints the same figure twice.
 *
 * Null when there is nothing to split.
 */
function speedBands(speeds) {
  const known = speeds.filter((speed) => speed != null).sort((a, b) => a - b)
  if (known.length < ORDINAL_RAMP.light.length) return null

  const edges = [0.2, 0.4, 0.6, 0.8].map(
    (fraction) => known[Math.floor(fraction * (known.length - 1))],
  )
  if (edges[0] === edges[edges.length - 1]) return null
  return { edges, slowest: known[0], fastest: known[known.length - 1] }
}

function bandOf(speed, edges) {
  if (speed == null) return null
  let band = 0
  while (band < edges.length && speed > edges[band]) band += 1
  return band
}

/**
 * Consecutive segments of the same band, as one polyline each.
 *
 * One element per segment would be hundreds of nodes for a long ride. Runs of
 * one colour are the natural shape and there are far fewer of them; each run
 * repeats its predecessor's last point, so the line has no gaps.
 */
function runsOf(points, speeds, edges) {
  const grouped = []
  let current = null

  for (let index = 0; index < speeds.length; index += 1) {
    const band = edges ? bandOf(speeds[index], edges) : null
    if (current === null || current.band !== band) {
      if (current) grouped.push(current)
      // Keyed by where it starts, not by its coordinates: two runs can begin at
      // the same place on a track that doubles back, and a repeated key is a
      // rendering bug that only shows up on some routes.
      current = { band, from: index, points: [points[index], points[index + 1]] }
    } else {
      current.points.push(points[index + 1])
    }
  }
  if (current) grouped.push(current)
  return grouped
}

/** Pointer position in viewBox units, accounting for the letterboxing. */
function toViewBox(rect, clientX, clientY) {
  if (!rect.width || !rect.height) return null
  // preserveAspectRatio defaults to xMidYMid meet: one uniform scale with the
  // longer axis padded and the drawing centred. Mapping the pointer as a plain
  // proportion of the element would land it somewhere else entirely on any box
  // that is not square, which is every box this is drawn in.
  const scale = Math.min(rect.width, rect.height) / VIEW_SIZE
  const padX = (rect.width - VIEW_SIZE * scale) / 2
  const padY = (rect.height - VIEW_SIZE * scale) / 2
  return {
    x: VIEW_MIN + (clientX - rect.left - padX) / scale,
    y: VIEW_MIN + (clientY - rect.top - padY) / scale,
  }
}

function nearestIndex(points, at) {
  let best = 0
  let bestDistance = Infinity
  for (let index = 0; index < points.length; index += 1) {
    const dx = points[index].x - at.x
    const dy = points[index].y - at.y
    const distance = dx * dx + dy * dy
    if (distance < bestDistance) {
      bestDistance = distance
      best = index
    }
  }
  return best
}

/**
 * The track, drawn as an SVG line with no basemap, coloured by speed.
 *
 * A tiled basemap would mean requesting map tiles for wherever you exercise,
 * which hands your neighbourhood to a third party — the opposite of the point
 * of self-hosting. What a bare line can still say is the shape of the route and
 * where on it you were moving, and that is what the colour is for.
 */
export default function RouteMap({ samples, sportType }) {
  const dark = useColorScheme()
  const ink = CHART_INK[dark ? 'dark' : 'light']
  const ramp = dark ? ORDINAL_RAMP.dark : ORDINAL_RAMP.light
  const plain = dark ? SINGLE_SERIES.dark : SINGLE_SERIES.light
  const [hover, setHover] = useState(null)

  const track = useMemo(() => {
    const points = project(samples)
    if (!points) return null
    const { distances, elapsed, speeds } = measure(points)
    const bands = speedBands(speeds)

    // The legend is the test of whether the encoding says anything at all. If
    // the slowest and the fastest stretch print as the same figure, five shades
    // are five names for one number and the reader is being asked to see a
    // difference that is below the precision anybody reports a pace in — so the
    // track goes back to being a plain line.
    const slowest = bands && formatRate(sportType, bands.slowest)
    const fastest = bands && formatRate(sportType, bands.fastest)
    const edges = bands && slowest !== fastest ? bands.edges : null

    return {
      points,
      distances,
      elapsed,
      speeds,
      edges,
      slowest,
      fastest,
      runs: runsOf(points, speeds, edges),
    }
  }, [samples, sportType])

  if (!track) {
    return <p className="text-xs muted">This activity has no position data.</p>
  }

  const { points, distances, elapsed, speeds, edges, slowest, fastest } = track
  const last = points.length - 1
  // Whether the file carried any timings at all, which is a different question
  // from whether the pointer happens to be at the start.
  const timed = elapsed[last] > 0
  // A stretch whose speed is unknown while the rest of the track is coloured
  // cannot wear a step of the ramp: the single-series blue happens to be the
  // ramp's middle step, so a lost signal would read as "average pace" rather
  // than "not measured". Grey says not measured. With no encoding at all there
  // is nothing to be mistaken for, so the plain line stays plain.
  const unknown = edges ? ink.axis : plain
  const hasUnknown = Boolean(edges) && speeds.some((speed) => speed == null)
  // A coloured line needs more width than a plain one: five steps of a single
  // hue are what carries the reading, and at the thickness that suits a bare
  // route they were nearly indistinguishable on the rendered page.
  const width = edges ? '3' : '1.6'

  function move(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    const at = toViewBox(rect, event.clientX, event.clientY)
    if (!at) return
    setHover({
      index: nearestIndex(points, at),
      left: event.clientX - rect.left,
      top: event.clientY - rect.top,
    })
  }

  // The hovered point's own speed: the hop that arrived there, or for the very
  // first point the one that leaves it.
  const hoveredSpeed = hover ? (speeds[hover.index - 1] ?? speeds[hover.index] ?? null) : null

  return (
    <figure className="relative m-0">
      <svg
        viewBox={`${VIEW_MIN} ${VIEW_MIN} ${VIEW_SIZE} ${VIEW_SIZE}`}
        className="h-56 w-full touch-none"
        role="img"
        aria-label={
          edges
            ? 'Route shape for this activity, coloured by speed'
            : 'Route shape for this activity'
        }
        onPointerMove={move}
        onPointerLeave={() => setHover(null)}
      >
        {track.runs.map((run) => (
          <polyline
            key={run.from}
            points={run.points
              .map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`)
              .join(' ')}
            fill="none"
            stroke={run.band == null ? unknown : ramp[run.band]}
            strokeWidth={width}
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        ))}

        {/* Start is a disc and finish a square: the two are told apart by shape,
            not by colour. Green against red is the obvious choice and fails
            outright for a red-green reader — those two sit 4.1 ΔE apart under
            simulated deuteranopia, where 8 is the target. The ring in the
            surface colour keeps both legible where the track crosses itself. */}
        <circle
          cx={points[0].x}
          cy={points[0].y}
          r="2.4"
          fill={ink.marker}
          stroke={ink.surface}
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        >
          <title>Start</title>
        </circle>
        <rect
          x={points[last].x - 2.1}
          y={points[last].y - 2.1}
          width="4.2"
          height="4.2"
          fill={ink.marker}
          stroke={ink.surface}
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        >
          <title>Finish</title>
        </rect>

        {hover && (
          <circle
            cx={points[hover.index].x}
            cy={points[hover.index].y}
            r="2.6"
            fill="none"
            stroke={ink.marker}
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>

      {hover && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md border px-2 py-1 text-xs tabular-nums shadow-sm"
          style={{
            left: hover.left,
            top: hover.top - 8,
            background: ink.tooltipBg,
            borderColor: ink.grid,
            color: ink.tooltipInk,
          }}
        >
          <div>{formatDistance(distances[hover.index])} in</div>
          {/* Only for a track that has timings at all — but then the start
              reads "0s" rather than dropping the line and resizing the
              tooltip as the pointer moves over it. */}
          {timed && <div>{formatElapsed(elapsed[hover.index])}</div>}
          {hoveredSpeed != null && <div>{formatRate(sportType, hoveredSpeed)}</div>}
        </div>
      )}

      {edges && (
        <figcaption className="mt-1 flex items-center justify-center gap-2 text-xs muted">
          <span>{slowest}</span>
          <span className="flex" aria-hidden="true">
            {ramp.map((step, band) => (
              <span
                key={step}
                className="h-2 w-5"
                style={{
                  background: step,
                  borderTopLeftRadius: band === 0 ? 2 : 0,
                  borderBottomLeftRadius: band === 0 ? 2 : 0,
                  borderTopRightRadius: band === ramp.length - 1 ? 2 : 0,
                  borderBottomRightRadius: band === ramp.length - 1 ? 2 : 0,
                }}
              />
            ))}
          </span>
          <span>{fastest}</span>
          {/* A mark on the chart that the legend does not explain is a mark the
              reader has to guess at. */}
          {hasUnknown && (
            <span className="ml-1 flex items-center gap-1">
              <span
                className="h-2 w-5 rounded-sm"
                style={{ background: ink.axis }}
                aria-hidden="true"
              />
              no signal
            </span>
          )}
        </figcaption>
      )}
    </figure>
  )
}
