import { useMemo } from 'react'
import { SINGLE_SERIES } from '../theme'
import { useColorScheme } from '../hooks/useColorScheme'

/**
 * The track, drawn as a plain SVG line with no basemap.
 *
 * A tiled basemap would mean requesting map tiles for wherever you exercise,
 * which hands your neighbourhood to a third party — the opposite of the point
 * of self-hosting. The shape of the route is what the line is for; a basemap
 * can be added later if that trade is worth making.
 */
export default function RouteMap({ samples }) {
  const dark = useColorScheme()
  const colour = dark ? SINGLE_SERIES.dark : SINGLE_SERIES.light

  const path = useMemo(() => {
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
    const scale = Math.min(100 / spanX, 100 / spanY)
    const offsetX = (100 - spanX * scale) / 2
    const offsetY = (100 - spanY * scale) / 2

    return located
      .map((sample) => {
        const x = offsetX + (sample.longitude - minLon) * Math.cos(midLat) * scale
        // SVG y grows downwards; north should be up.
        const y = offsetY + (maxLat - sample.latitude) * scale
        return `${x.toFixed(2)},${y.toFixed(2)}`
      })
      .join(' ')
  }, [samples])

  if (!path) {
    return (
      <p className="text-xs muted">
        This activity has no position data.
      </p>
    )
  }

  return (
    <svg
      viewBox="-4 -4 108 108"
      className="h-56 w-full"
      role="img"
      aria-label="Route shape for this activity"
    >
      <polyline
        points={path}
        fill="none"
        stroke={colour}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}
