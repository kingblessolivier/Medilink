import { useI18n } from "../i18n"
import { roundTo5, timeAgo } from "../lib/format"
import type { Wait } from "../api/types"

/**
 * Where the honesty rule reaches the screen.
 *
 * Unknown data must look visually quieter than known data, so a patient can
 * tell the difference at a glance without reading. Never invent a number.
 */
export function WaitLine({ wait }: { wait: Wait }) {
  const { t, lang } = useI18n()

  switch (wait.status) {
    case "available":
      return (
        <p className="mt-1 text-sm">
          {t("wait_about", { minutes: roundTo5(wait.minutes ?? 0) })}
          <span className="ml-1 text-neutral-400">
            {"·"} {t("updated_ago", { ago: timeAgo(wait.as_of, lang) })}
          </span>
        </p>
      )
    case "closed":
      return <p className="mt-1 text-sm text-neutral-500">{t("closed")}</p>
    case "not_reported":
    case "insufficient_data":
      return (
        <p className="mt-1 text-sm text-neutral-500">{t("wait_unavailable")}</p>
      )
  }
}
