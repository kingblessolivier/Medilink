import { useCallback, useState } from "react"

const STORAGE_KEY = "medilink.insurer"

/**
 * The insurance filter is set once and applies to every list. Keeping it
 * visible on the home screen - rather than buried in settings - is what makes
 * the core promise of the product legible.
 */
export function useInsurerPreference() {
  const [insurer, setInsurerState] = useState<string | undefined>(
    () => localStorage.getItem(STORAGE_KEY) ?? undefined,
  )

  const setInsurer = useCallback((code: string | undefined) => {
    if (code) localStorage.setItem(STORAGE_KEY, code)
    else localStorage.removeItem(STORAGE_KEY)
    setInsurerState(code)
  }, [])

  return { insurer, setInsurer }
}
