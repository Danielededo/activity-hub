const REPOSITORY = 'https://github.com/Danielededo/activity-hub'

/**
 * Says where this app came from.
 *
 * Someone can arrive in front of a running Activity Hub without having been
 * the one who deployed it — a NAS in the house, a server someone set up years
 * ago — and the running app is then the only clue they have. So the footer
 * carries the link out to the project and its licence.
 *
 * Rendered on every screen, including the one that reports an unreachable API:
 * a person whose stack will not come up is exactly the person who wants the
 * repository, and that screen is where they are stuck.
 */
export default function Footer() {
  return (
    <footer className="mt-12 border-t border-[var(--border)]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-6 text-xs">
        <p className="muted">Activity Hub — your training, on your own machine.</p>

        {/* Underlined, not merely coloured: these sit in body ink, so colour
            alone would not say they are links. */}
        <p className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <a
            href={REPOSITORY}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 underline underline-offset-2"
          >
            <GitHubMark />
            Source on GitHub
          </a>
          <a
            href={`${REPOSITORY}/blob/main/LICENSE`}
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-2"
          >
            MIT licence
          </a>
        </p>
      </div>
    </footer>
  )
}

/** The mark people scan a footer for. Decorative: the link text carries it. */
function GitHubMark() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.4 7.4 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A7.99 7.99 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  )
}
