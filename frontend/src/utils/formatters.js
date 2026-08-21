/**
 * Metric formatting. The API is metric and so is the UI — no unit toggle.
 *
 * Runners read minutes per kilometre and cyclists read kilometres per hour, so
 * the pace helper picks by sport rather than showing one and making the other
 * do arithmetic.
 */

const PACE_SPORTS = new Set(['running', 'hiking', 'walking'])

export function formatDistance(metres) {
  if (metres == null) return '—'
  if (metres < 1000) return `${Math.round(metres)} m`
  return `${(metres / 1000).toFixed(1)} km`
}

export function formatDuration(seconds) {
  if (seconds == null || seconds <= 0) return '—'
  const total = Math.round(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, '0')}m`
  return `${minutes}m ${String(total % 60).padStart(2, '0')}s`
}

export function formatElevation(metres) {
  if (metres == null) return '—'
  return `${Math.round(metres)} m`
}

export function formatHeartRate(bpm) {
  return bpm == null ? '—' : `${Math.round(bpm)} bpm`
}

export function formatCadence(rpm) {
  return rpm == null ? '—' : `${Math.round(rpm)} rpm`
}

/** Minutes per kilometre for foot sports, km/h for everything else. */
export function formatPaceOrSpeed(sportType, metres, seconds) {
  if (!metres || !seconds) return '—'
  if (PACE_SPORTS.has(sportType)) {
    const secondsPerKm = seconds / (metres / 1000)
    const minutes = Math.floor(secondsPerKm / 60)
    const rest = Math.round(secondsPerKm % 60)
    // 4:60 /km is not a pace anybody writes.
    const carried = rest === 60 ? [minutes + 1, 0] : [minutes, rest]
    return `${carried[0]}:${String(carried[1]).padStart(2, '0')} /km`
  }
  return `${(metres / seconds * 3.6).toFixed(1)} km/h`
}

export function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

/**
 * The activity's own local time, using the offset its file stated.
 *
 * Always 24-hour HH:MM. Falling back to the viewer's locale for the no-offset
 * case put "06:45 PM" and "08:45" in the same column, which reads as two
 * different kinds of number rather than two activities.
 */
export function formatLocalTime(iso, utcOffsetMinutes) {
  if (!iso) return '—'
  const moment = new Date(iso)
  const stated = utcOffsetMinutes != null
  const shifted = stated ? new Date(moment.getTime() + utcOffsetMinutes * 60_000) : moment
  const hours = stated ? shifted.getUTCHours() : shifted.getHours()
  const minutes = stated ? shifted.getUTCMinutes() : shifted.getMinutes()
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

export function sportLabel(sportType) {
  if (!sportType) return 'Other'
  return sportType.charAt(0).toUpperCase() + sportType.slice(1)
}

export function formatWeek(weekStart) {
  return new Date(weekStart).toLocaleDateString(undefined, { day: '2-digit', month: 'short' })
}
