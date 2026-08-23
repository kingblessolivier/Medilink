import { useI18n } from "../i18n"
import { useOnline } from "../hooks/useOnline"
import { Notice } from "../ui"
import { timeAgo } from "../lib/format"

/**
 * "You are looking at saved results, from this long ago."
 *
 * The query cache holds facility results for a day so the app still shows
 * something with no connection - which is the right behaviour on a Kigali
 * bus. But without saying WHEN, a patient reads a saved wait time as a live
 * one and travels on it. docs/04 requires the timestamp for exactly that
 * reason.
 *
 * Only rendered offline. Online, the data either refreshed or the error state
 * says it did not; a permanent "last updated" line on a live screen is noise
 * that trains people to ignore it.
 */
export function CachedNotice({ updatedAt }: { updatedAt: number | undefined }) {
  const { t, lang } = useI18n()
  const online = useOnline()

  if (online || !updatedAt) return null

  return (
    <Notice tone="warning">
      {t("cached_results", { ago: timeAgo(new Date(updatedAt).toISOString(), lang) })}
    </Notice>
  )
}
