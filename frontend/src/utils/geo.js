/**
 * Distance on the ground, for turning samples into speeds.
 *
 * The same formula and radius the backend uses, so a segment measured here
 * agrees with the totals it computed.
 */

const EARTH_RADIUS_M = 6_371_008.8

/** Great-circle distance between two coordinates, in metres. */
export function haversineDistance(lat1, lon1, lat2, lon2) {
  const toRadians = Math.PI / 180
  const phi1 = lat1 * toRadians
  const phi2 = lat2 * toRadians
  const deltaPhi = phi2 - phi1
  const deltaLambda = (lon2 - lon1) * toRadians
  const inner =
    Math.sin(deltaPhi / 2) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(Math.min(1, inner)))
}
