import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Footer from '../src/components/Footer'

const REPOSITORY = 'https://github.com/Danielededo/activity-hub'

describe('Footer', () => {
  it('is a footer landmark', () => {
    render(<Footer />)

    expect(screen.getByRole('contentinfo')).toBeVisible()
  })

  it('links out to the project', () => {
    render(<Footer />)

    const source = screen.getByRole('link', { name: /source on github/i })
    expect(source).toHaveAttribute('href', REPOSITORY)
  })

  it('links to the licence itself, not just its name', () => {
    render(<Footer />)

    expect(screen.getByRole('link', { name: /mit licence/i })).toHaveAttribute(
      'href',
      `${REPOSITORY}/blob/main/LICENSE`,
    )
  })

  it('opens outward links in a new tab without handing over the referrer', () => {
    // The app is self-hosted; navigating away from it should not close it, and
    // a local address is nobody else's business.
    render(<Footer />)

    for (const link of screen.getAllByRole('link')) {
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noreferrer')
    }
  })

  it('does not rely on colour to say a link is a link', () => {
    render(<Footer />)

    for (const link of screen.getAllByRole('link')) {
      expect(link.className).toMatch(/underline/)
    }
  })

  it('hides the decorative mark from a screen reader', () => {
    // The link text already says where it goes; the mark would only repeat it.
    const { container } = render(<Footer />)

    const svg = container.querySelector('svg')
    expect(svg).toHaveAttribute('aria-hidden', 'true')
  })
})
