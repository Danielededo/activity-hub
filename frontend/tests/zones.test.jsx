import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import HeartRateZones from '../src/components/HeartRateZones'
import ZoneBar from '../src/components/ZoneBar'
import { zoneRange, zoneShares, zonedSeconds } from '../src/utils/zones'

const NAMES = ['Recovery', 'Endurance', 'Tempo', 'Threshold', 'VO2 max']

function bands(seconds) {
  return seconds.map((value, index) => ({
    zone: index + 1,
    name: NAMES[index],
    min_bpm: 100 + index * 20,
    max_bpm: index === 4 ? null : 119 + index * 20,
    seconds: value,
  }))
}

const SUMMARY = {
  user_id: 1,
  max_heart_rate: 200,
  max_heart_rate_source: 'observed',
  weeks: 4,
  zones: bands([600, 3_600, 1_200, 600, 120]),
  seconds_below_zones: 300,
  total_load: 210,
  weekly: [
    { week_start: '2026-06-01', load: 0, seconds: bands([0, 0, 0, 0, 0]).map((b) => ({ zone: b.zone, seconds: 0 })) },
    { week_start: '2026-06-08', load: 120, seconds: [{ zone: 1, seconds: 300 }, { zone: 2, seconds: 1_800 }, { zone: 3, seconds: 600 }, { zone: 4, seconds: 0 }, { zone: 5, seconds: 0 }] },
  ],
}

describe('zone helpers', () => {
  it('totals only the time that landed in a zone', () => {
    expect(zonedSeconds(bands([100, 200, 0, 0, 0]))).toBe(300)
  })

  it('survives a breakdown with nothing in it', () => {
    expect(zonedSeconds([])).toBe(0)
    expect(zoneShares([]).length).toBe(0)
    expect(zoneShares(bands([0, 0, 0, 0, 0])).every((band) => band.share === 0)).toBe(true)
  })

  it('gives each zone its share of the time in zone', () => {
    const shares = zoneShares(bands([300, 900, 0, 0, 0]))

    expect(shares[0].share).toBeCloseTo(0.25)
    expect(shares[1].share).toBeCloseTo(0.75)
  })

  it('leaves the top zone open ended', () => {
    expect(zoneRange({ min_bpm: 100, max_bpm: 119 })).toBe('100–119 bpm')
    expect(zoneRange({ min_bpm: 180, max_bpm: null })).toBe('180+ bpm')
  })
})

describe('ZoneBar', () => {
  it('names each zone in text, not by colour alone', () => {
    render(<ZoneBar zones={bands([600, 1_200, 0, 0, 0])} load={45} />)

    expect(screen.getByText(/Z1 Recovery/)).toBeInTheDocument()
    expect(screen.getByText(/Z2 Endurance/)).toBeInTheDocument()
  })

  it('lists only the zones that carry time', () => {
    // A steady endurance ride should not list four blank zones.
    render(<ZoneBar zones={bands([0, 1_200, 0, 0, 0])} load={40} />)

    expect(screen.getByText(/Z2 Endurance/)).toBeInTheDocument()
    expect(screen.queryByText(/Z5/)).not.toBeInTheDocument()
  })

  it('shows the load it earned', () => {
    render(<ZoneBar zones={bands([600, 0, 0, 0, 0])} load={45.6} />)

    expect(screen.getByText('46')).toBeInTheDocument()
  })

  it('draws nothing at all for an activity with no heart rate', () => {
    const { container } = render(<ZoneBar zones={[]} load={0} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('draws nothing when every zone is empty', () => {
    const { container } = render(<ZoneBar zones={bands([0, 0, 0, 0, 0])} load={0} />)

    expect(container).toBeEmptyDOMElement()
  })
})

describe('HeartRateZones', () => {
  function renderPanel(props = {}) {
    return render(
      <HeartRateZones summary={SUMMARY} weeks={4} onWeeksChange={vi.fn()} {...props} />,
    )
  }

  it('lists all five zones with their beat ranges', () => {
    renderPanel()

    for (const name of NAMES) {
      expect(screen.getByText(new RegExp(name))).toBeInTheDocument()
    }
    expect(screen.getByText('180+ bpm')).toBeInTheDocument()
  })

  it('says where the maximum came from', () => {
    // An observed maximum is a floor, not a maximum: a reader who has never
    // pushed to theirs needs to know the zones are built on a guess.
    renderPanel()

    expect(screen.getByText(/max 200 bpm \(observed\)/)).toBeInTheDocument()
  })

  it('reports the time below zone one instead of folding it in', () => {
    renderPanel()

    expect(screen.getByText(/below Z1, warming up or standing still/)).toBeInTheDocument()
  })

  it('says nothing about time below zone one when there was none', () => {
    renderPanel({ summary: { ...SUMMARY, seconds_below_zones: 0 } })

    expect(screen.queryByText(/below Z1/)).not.toBeInTheDocument()
  })

  it('explains what the load figure is', () => {
    renderPanel()

    expect(screen.getByText(/Edwards/)).toBeInTheDocument()
    expect(screen.getByText('210')).toBeInTheDocument()
  })

  it('changes the reporting range', async () => {
    const onWeeksChange = vi.fn()
    renderPanel({ onWeeksChange })

    await userEvent.selectOptions(screen.getByLabelText(/range/i), '26')

    expect(onWeeksChange).toHaveBeenCalledWith(26)
  })

  it('explains an absent heart rate rather than showing an empty chart', () => {
    renderPanel({ summary: { ...SUMMARY, zones: [], max_heart_rate: null } })

    expect(screen.getByText(/no heart rate recorded yet/i)).toBeInTheDocument()
  })

  it('distinguishes no heart rate from no time in zone', () => {
    renderPanel({ summary: { ...SUMMARY, zones: [], max_heart_rate: 190 } })

    expect(screen.getByText(/no time in zone yet/i)).toBeInTheDocument()
  })

  it('survives the render before the request has answered', () => {
    renderPanel({ summary: null })

    expect(screen.getByText(/no heart rate recorded yet/i)).toBeInTheDocument()
  })
})
