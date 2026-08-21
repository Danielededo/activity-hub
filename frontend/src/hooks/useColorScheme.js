import { useEffect, useState } from 'react'

const QUERY = '(prefers-color-scheme: dark)'

/** Whether the viewer is in dark mode, kept in sync if they switch. */
export function useColorScheme() {
  const [dark, setDark] = useState(
    () => typeof window !== 'undefined' && window.matchMedia?.(QUERY).matches === true,
  )

  useEffect(() => {
    const media = window.matchMedia?.(QUERY)
    if (!media) return
    const listen = (event) => setDark(event.matches)
    media.addEventListener('change', listen)
    return () => media.removeEventListener('change', listen)
  }, [])

  return dark
}
