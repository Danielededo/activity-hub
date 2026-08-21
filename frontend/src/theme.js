/**
 * The categorical palette, in fixed slot order.
 *
 * Both modes come from a validated reference palette: every hue clears the
 * lightness band, chroma floor, colour-vision-deficiency separation and
 * normal-vision floor against its own surface. Do not reorder these and do not
 * add a fifth by picking something that looks nice — colour follows the entity,
 * and an unvalidated hue can be invisible to a colourblind reader.
 *
 * Two light slots sit below 3:1 contrast on white, so anything painted with
 * them carries a visible direct label. The workout table is the table view.
 */
const LIGHT = {
  cycling: '#2a78d6',
  running: '#eb6834',
  hiking: '#1baf7a',
  other: '#eda100',
}

const DARK = {
  cycling: '#3987e5',
  running: '#d95926',
  hiking: '#199e70',
  other: '#c98500',
}

export const SPORT_ORDER = ['cycling', 'running', 'hiking', 'other']

/** The single hue used when a chart shows one measure and needs no identity. */
export const SINGLE_SERIES = { light: '#2a78d6', dark: '#3987e5' }

export const CHART_INK = {
  light: {
    grid: '#e2e8f0',
    axis: '#64748b',
    tooltipBg: '#ffffff',
    tooltipInk: '#0f172a',
    // The panel behind a chart, for the ring that keeps a marker legible where
    // it crosses a line.
    surface: '#ffffff',
    // Landmarks are not data: start and finish wear text ink, never a step of
    // the speed ramp, or they would read as a speed.
    marker: '#0f172a',
  },
  dark: {
    grid: '#3a3a38',
    axis: '#a3a3a0',
    tooltipBg: '#1f1f1e',
    tooltipInk: '#f5f5f4',
    surface: '#1f1f1e',
    marker: '#f5f5f4',
  },
}

/**
 * Five ordinal steps of one hue, low to high, for any ordered five-way scale.
 *
 * Used for route speed and for heart-rate zones. One ramp rather than two
 * because the documented palette specifies steps for a single sequential hue,
 * and inventing a second by eye is the one thing the colour method forbids. The
 * two never share a screen — speed lives on an activity's route, zones on the
 * dashboard — so there is nothing for a reader to confuse.
 *
 * Ordinal rather than the full sequential range: every step has to stay visible
 * against the panel, because the pale end here means "the low end of a scale",
 * not "absent" — a step that receded into the surface would vanish. Both modes
 * clear the 2:1 floor for the step nearest their own surface (2.11:1 on white,
 * 2.04:1 on the dark panel), are monotone in lightness with gaps of at least
 * 0.06, and hold to a 3° hue spread. Validated, not chosen by eye; re-run the
 * check before touching a value.
 *
 * Dark is not the light ramp flipped: it is stepped from the same hue against
 * the dark surface, which is why its ends are 600 and 200 rather than 650 and
 * 250.
 */
export const ORDINAL_RAMP = {
  light: ['#86b6ef', '#5598e7', '#2a78d6', '#1c5cab', '#104281'],
  dark: ['#184f95', '#256abf', '#3987e5', '#6da7ec', '#9ec5f4'],
}

export function sportColor(sport, dark = false) {
  const palette = dark ? DARK : LIGHT
  return palette[sport] ?? palette.other
}

export function palette(dark = false) {
  return dark ? DARK : LIGHT
}
