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
  light: { grid: '#e2e8f0', axis: '#64748b', tooltipBg: '#ffffff', tooltipInk: '#0f172a' },
  dark: { grid: '#3a3a38', axis: '#a3a3a0', tooltipBg: '#1f1f1e', tooltipInk: '#f5f5f4' },
}

export function sportColor(sport, dark = false) {
  const palette = dark ? DARK : LIGHT
  return palette[sport] ?? palette.other
}

export function palette(dark = false) {
  return dark ? DARK : LIGHT
}
