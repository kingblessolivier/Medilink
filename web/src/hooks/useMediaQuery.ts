import { useEffect, useState } from "react"

/**
 * Subscribe to a media query from JS.
 *
 * For the cases where a breakpoint changes WHAT IS FETCHED OR RENDERED, not
 * just how it looks. Anything purely visual belongs in a Tailwind `md:`
 * class - CSS handles it without a re-render and without shipping the
 * hidden markup to a phone.
 *
 * Returns false during the first render on the server or before the effect
 * runs, so callers should treat false as "narrow" - the mobile layout is the
 * safe default to flash.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false
    return window.matchMedia(query).matches
  })

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return
    const list = window.matchMedia(query)
    const onChange = (event: MediaQueryListEvent) => setMatches(event.matches)
    // Sync once in case the query changed between render and effect.
    setMatches(list.matches)
    list.addEventListener("change", onChange)
    return () => list.removeEventListener("change", onChange)
  }, [query])

  return matches
}
