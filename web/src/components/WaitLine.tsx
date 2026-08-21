import { useI18n } from "../i18n"
import { Chip, type ChipTone } from "../ui"
import { roundTo5, timeAgo } from "../lib/format"
import type { Wait, WaitStatus } from "../api/types"

/**
 * Where the honesty rule reaches the screen.
 *
 * Four states, and only one of them may carry a number. The `unknown` tone is
 * the quietest in the design system on purpose: a patient must be able to tell
 * "we do not know" from "we know" at a glance, without reading the words.
 *
 * There is deliberately no "estimated" state. We never guess a wait time.
 */

const TONE: Record<WaitStatus, ChipTone> = {
  available: "success",
  closed: "neutral",
  not_reported: "unknown",
  insufficient_data: "unknown",
}

export function WaitLine({ wait, className }: { wait: Wait; className?: string }) {
  const { t, lang } = useI18n()
  const tone = TONE[wait.status]

  if (wait.status === "available") {
    return (
      <div className={className}>
        <Chip tone={tone}>
          {t("wait_about", { minutes: roundTo5(wait.minutes ?? 0) })}
        </Chip>
        {/* Staleness is never hidden. A stale number that looks live is worse
            than no number at all. */}
        <span className="ml-2 text-caption text-ink-subtle">
          {t("updated_ago", { ago: timeAgo(wait.as_of, lang) })}
        </span>
      </div>
    )
  }

  if (wait.status === "closed") {
    return (
      <div className={className}>
        <Chip tone={tone}>{t("closed")}</Chip>
      </div>
    )
  }

  return (
    <div className={className}>
      <Chip tone={tone}>{t("wait_unavailable")}</Chip>
    </div>
  )
}
