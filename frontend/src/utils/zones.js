/**
 * Shared reading of a zone breakdown.
 *
 * Both the dashboard panel and the activity detail need the same three things
 * from the API's answer, and neither should re-derive them differently.
 */

/** Seconds across all five zones, ignoring time below the first one. */
export function zonedSeconds(zones) {
  return (zones ?? []).reduce((total, band) => total + band.seconds, 0)
}

/** Each zone's share of the time actually spent in a zone, 0–1. */
export function zoneShares(zones) {
  const total = zonedSeconds(zones)
  return (zones ?? []).map((band) => ({
    ...band,
    share: total > 0 ? band.seconds / total : 0,
  }))
}

/** How a zone's range reads: "120–139 bpm", and "180+ bpm" for the top one. */
export function zoneRange(band) {
  return band.max_bpm == null ? `${band.min_bpm}+ bpm` : `${band.min_bpm}–${band.max_bpm} bpm`
}
