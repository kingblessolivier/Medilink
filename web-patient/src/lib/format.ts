export function formatDistance(metres: number, nearbyLabel: string): string {
  if (metres < 100) return nearbyLabel
  if (metres < 1000) return `${Math.round(metres / 50) * 50} m`
  return `${(metres / 1000).toFixed(1)} km`
}

/**
 * Rendering "43 minutes" claims a precision we do not have.
 * "About 45 min" is honest and reads as an estimate.
 */
export function roundTo5(minutes: number): number {
  return Math.max(5, Math.round(minutes / 5) * 5)
}

export function timeAgo(isoString: string, lang: string): string {
  const seconds = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000)
  const minutes = Math.floor(seconds / 60)

  const units: Record<string, [string, string]> = {
    rw: ["ubu", "iminota"],
    en: ["just now", "min"],
    fr: ["a l'instant", "min"],
  }
  const [now, minLabel] = units[lang] ?? units.en

  if (minutes < 1) return now
  return lang === "rw" ? `${minLabel} ${minutes}` : `${minutes} ${minLabel}`
}
