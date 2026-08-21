import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ExportPanel from '../src/components/ExportPanel'
import { exportUrl } from '../src/api/client'
import { EMPTY_FILTERS } from '../src/components/FilterBar'

describe('exportUrl', () => {
  it('carries the user and nothing else when nothing is filtered', () => {
    const url = new URL(exportUrl('/export/activities.csv', { userId: 7 }), 'http://x')

    expect(url.pathname).toBe('/api/export/activities.csv')
    expect([...url.searchParams]).toEqual([['user_id', '7']])
  })

  it('passes the filters through so the file matches the screen', () => {
    const url = new URL(
      exportUrl('/export/activities.zip', {
        userId: 7,
        sportType: 'running',
        dateFrom: '2026-07-01',
        dateTo: '2026-07-31',
        q: 'hill',
      }),
      'http://x',
    )

    expect(url.searchParams.get('sport_type')).toBe('running')
    expect(url.searchParams.get('date_from')).toBe('2026-07-01')
    expect(url.searchParams.get('date_to')).toBe('2026-07-31')
    expect(url.searchParams.get('q')).toBe('hill')
  })

  it('leaves an empty filter out rather than sending a blank', () => {
    // sport_type= is a filter for the sport named "", which matches nothing.
    const url = new URL(
      exportUrl('/export/activities.csv', { userId: 7, sportType: '', q: '' }),
      'http://x',
    )

    expect(url.searchParams.has('sport_type')).toBe(false)
    expect(url.searchParams.has('q')).toBe(false)
  })

  it('escapes a search term rather than breaking the query string', () => {
    const url = new URL(
      exportUrl('/export/activities.csv', { userId: 7, q: 'a&b=c d' }),
      'http://x',
    )

    expect(url.searchParams.get('q')).toBe('a&b=c d')
  })
})

describe('ExportPanel', () => {
  it('offers both formats as links, so the browser does the download', () => {
    render(<ExportPanel userId={7} filters={EMPTY_FILTERS} total={42} />)

    const csv = screen.getByRole('link', { name: /csv/i })
    const zip = screen.getByRole('link', { name: /tracks as gpx/i })

    expect(csv).toHaveAttribute('href', expect.stringContaining('activities.csv'))
    expect(zip).toHaveAttribute('href', expect.stringContaining('activities.zip'))
  })

  it('does not promise "all" when the export is filtered', () => {
    // The link and the sentence above it were contradicting each other.
    render(
      <ExportPanel userId={7} filters={{ ...EMPTY_FILTERS, sportType: 'hiking' }} total={3} />,
    )

    expect(screen.getByRole('link', { name: /tracks as gpx/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /all activities/i })).not.toBeInTheDocument()
  })

  it('says it will export everything when nothing is filtered', () => {
    render(<ExportPanel userId={7} filters={EMPTY_FILTERS} total={42} />)

    expect(screen.getByText(/everything you have uploaded/i)).toBeInTheDocument()
  })

  it('says how much a filtered export will contain', () => {
    // Downloading a filtered export and finding it short is worse than being
    // told before clicking.
    render(
      <ExportPanel userId={7} filters={{ ...EMPTY_FILTERS, sportType: 'running' }} total={12} />,
    )

    expect(screen.getByText(/the 12 activities matching the filters above/i)).toBeInTheDocument()
  })

  it('counts one activity in the singular', () => {
    render(<ExportPanel userId={7} filters={{ ...EMPTY_FILTERS, q: 'hill' }} total={1} />)

    expect(screen.getByText(/the 1 activity matching/i)).toBeInTheDocument()
  })

  it('sends the filters to the download links, not just to the wording', () => {
    render(
      <ExportPanel userId={7} filters={{ ...EMPTY_FILTERS, sportType: 'hiking' }} total={3} />,
    )

    for (const link of screen.getAllByRole('link')) {
      expect(link.getAttribute('href')).toContain('sport_type=hiking')
    }
  })

  it('explains why there are two formats rather than one', () => {
    render(<ExportPanel userId={7} filters={EMPTY_FILTERS} total={42} />)

    expect(screen.getByText(/nowhere to put a device/i)).toBeInTheDocument()
  })
})
