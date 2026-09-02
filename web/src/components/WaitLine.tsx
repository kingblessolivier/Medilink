import { useI18n } from "../i18n"
import { Chip, type ChipTone } from "../ui"
import { roundTo5, timeAgo } from "../lib/format"
import type { Wait, WaitStatus } from "../api/types"

/**
 * Where the honesty rule reaches the screen.
 *
 * Four states, and only one of them may carry a number. A patient must be able
 * to tell "we do not know" from "we know" at a glance, without reading the
 * words.
 *
 * There is deliberately no "estimated" state. We never guess a wait time.
 */

const TONE: Record<WaitStatus, ChipTone> = {
  available: "success",
  closed: "neutral",
  not_reported: "unknown",
  insufficient_data: "unknown",
}

/**
 * `not_reported` and `insufficient_data` deliberately share one sentence.
 *
 * The API keeps them apart because operations needs to know which is which -
 * "this facility runs no reception tool" is a sales problem, "this one has
 * too few samples yet" is a time problem. A patient has no use for that
 * distinction: both mean we do not know, and explaining our data collection
 * to somebody deciding whether to travel is noise, not honesty.
 *
 * Recorded here because it looks like an oversight and is not.
 */

export function isWaitKnown(wait: Wait): boolean {
  return wait.status === "available"
}

/**
 * Unknown wait times are TEXT, not a chip.
 *
 * They used to render as a bordered pill, the same shape as "Open until 12:00"
 * next to it. Because almost no facility reports live queue data yet, a
 * results page showed six identical grey pills all saying the same thing, and
 * a facility page showed one per service - which reads as six broken widgets
 * rather than as one honest absence.
 *
 * A pill is for a fact worth scanning. "We do not know" is worth stating once,
 * quietly, in the flow of the text. Rule 4 of the design system - unknown data
 * is the quietest thing on screen - is better served by weight and colour than
 * by drawing a box around it.
 *
 * Callers with many rows should pass `omitUnknown` and explain the absence
 * once at section level instead. See FacilityDetail's availability list.
 */
export function WaitLine({
  wait,
  className,
  omitUnknown = false,
}: {
  wait: Wait
  className?: string
  omitUnknown?: boolean
}) {
  const { t, lang } = useI18n()

  if (wait.status === "available") {
    return (
      <div className={className}>
        <Chip tone={TONE.available}>
          {t("wait_about", { minutes: roundTo5(wait.minutes ?? 0) })}
        </Chip>
        {/* Staleness is never hidden. A stale number that looks live is worse
            than no number at all. */}
        <span className="ml-2 text-label text-n600">
          {t("updated_ago", { ago: timeAgo(wait.as_of, lang) })}
        </span>
      </div>
    )
  }

  if (wait.status === "closed") {
    return (
      <div className={className}>
        <Chip tone={TONE.closed}>{t("closed")}</Chip>
      </div>
    )
  }

  if (omitUnknown) return null

  return (
    <p className={className}>
      <span className="text-label text-n600">{t("wait_unavailable")}</span>
    </p>
  )
}
