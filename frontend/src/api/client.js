/** Everything this app knows how to ask the API. */

import axios from 'axios'

// Empty base URL means /api on the app's own origin — what the Vite dev proxy
// and the nginx image both serve, so no CORS is involved either way.
const baseURL = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api`

export const http = axios.create({ baseURL, timeout: 30_000 })

/** The API's `detail` if it sent one, so the UI can show the real reason. */
export function errorMessage(error, fallback = 'Something went wrong') {
  return error?.response?.data?.detail ?? error?.message ?? fallback
}

/** The profile, or null when nobody has introduced themselves yet. */
export async function fetchProfile() {
  try {
    const { data } = await http.get('/users/me')
    return data
  } catch (error) {
    if (error?.response?.status === 404) return null
    throw error
  }
}

export async function createProfile({ firstName, lastName }) {
  const { data } = await http.post('/users/', {
    first_name: firstName,
    last_name: lastName || null,
  })
  return data
}

/**
 * A page of activities, narrowed by whatever filters are set.
 *
 * Empty filter values are dropped rather than sent as blanks: `sport_type=`
 * would be a filter for the sport named "", which matches nothing.
 */
export async function fetchWorkouts({
  userId,
  limit = 20,
  offset = 0,
  sportType,
  dateFrom,
  dateTo,
  q,
}) {
  const { data } = await http.get('/workouts', {
    params: {
      user_id: userId,
      limit,
      offset,
      sport_type: sportType || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      q: q || undefined,
    },
  })
  return data
}

export async function fetchWorkout(workoutId, userId) {
  const { data } = await http.get(`/workouts/${workoutId}`, { params: { user_id: userId } })
  return data
}

export async function fetchTrackPoints(workoutId, userId, maxPoints = 600) {
  const { data } = await http.get(`/workouts/${workoutId}/track-points`, {
    params: { user_id: userId, max_points: maxPoints },
  })
  return data
}

export async function deleteWorkout(workoutId, userId) {
  await http.delete(`/workouts/${workoutId}`, { params: { user_id: userId } })
}

export async function fetchAnalysis(userId) {
  const { data } = await http.get(`/analysis/${userId}`)
  return data
}

/** Per-sport records and standard-distance bests, plus totals by year. */
export async function fetchRecords(userId) {
  const { data } = await http.get(`/analysis/${userId}/records`)
  return data
}

/** Time in each heart-rate zone, lifetime and by week, with training load. */
export async function fetchZones(userId, weeks = 12) {
  const { data } = await http.get(`/analysis/${userId}/zones`, { params: { weeks } })
  return data
}

/** One activity's time in zone. Empty when it recorded no heart rate. */
export async function fetchWorkoutZones(workoutId, userId) {
  const { data } = await http.get(`/workouts/${workoutId}/zones`, { params: { user_id: userId } })
  return data
}

export async function fetchWeekly(userId, weeks = 12) {
  const { data } = await http.get(`/analysis/${userId}/weekly`, { params: { weeks } })
  return data
}

export async function uploadWorkout(userId, file) {
  const body = new FormData()
  body.append('file', file)
  const { data } = await http.post('/upload', body, { params: { user_id: userId } })
  return data
}

/** Unpack an export archive. Returns counts plus a capped per-member list. */
export async function uploadArchive(userId, file) {
  const body = new FormData()
  body.append('file', file)
  const { data } = await http.post('/upload/archive', body, {
    params: { user_id: userId },
    // A full export is hundreds of files to parse and insert, one at a time.
    timeout: 10 * 60_000,
  })
  return data
}
