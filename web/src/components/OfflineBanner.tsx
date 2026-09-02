import { useI18n } from "../i18n"
import { useOnline } from "../hooks/useOnline"
import { IconAlert } from "../ui/icons"

/**
 * A standing bar while the connection is gone.
 *
 * Says only that the connection is gone. What the stale data on screen is
 * worth is CachedNotice's job, next to the data itself - a banner at the top
 * of the page cannot tell you how old the wait time three screens down is.
 */
export function OfflineBanner() {
  const { t } = useI18n()
  const online = useOnline()

  if (online) return null

  return (
    <p
      role="status"
      className="flex items-center justify-center gap-2 bg-warning px-4 py-2 text-center text-body text-white"
    >
      <IconAlert size={15} className="shrink-0" />
      {t("offline_banner")}
    </p>
  )
}
