/**
 * QueuePositionDisplay - the most important component in the product.
 *
 * It exists to produce one sentence honestly: "You are number 8. Leave home by
 * 10:15." Four rules, and none of them are styling:
 *
 * - A NULL ETA RENDERS "Wait time not available". Not a placeholder, not
 *   "calculating...", not an estimate from an average. A fabricated number
 *   destroys trust permanently, and it is the one thing this product cannot
 *   recover from. The null branch is the reason this component exists rather
 *   than a <p> tag.
 *
 * - A NULL leaveHomeBy HIDES THE SECTION ENTIRELY. There is no honest way to
 *   render half a departure time, and an empty row where a time should be
 *   reads as a loading state that never resolves.
 *
 * - STALE DATA SAYS SO. Past two minutes without an update the component says
 *   how old the number is, because a queue position that has stopped updating
 *   looks exactly like one that has not.
 *
 * - THE NUMBER ANIMATES WHEN IT CHANGES. It is 72px because it has to be
 *   readable at arm's length, held by somebody who is unwell, in a waiting
 *   room - and the one moment it matters most is the moment it ticks down.
 */

import { useEffect, useRef, useState } from "react"
import { useI18n } from "../i18n"

export type QueuePositionDisplayProps = {
  /** Places ahead of this patient, counted live. Never stored as a column. */
  position: number
  /** Null whenever the facility reports no live queue data. */
  etaMinutes: number | null
  /** Null unless an ETA and a travel time are both known. */
  leaveHomeBy: string | null
  totalAhead: number
  totalSeen: number
  updatedAt: Date
}

/** Past this, the number on screen is old enough that we have to say so. */
const STALE_AFTER_MS = 2 * 60 * 1000

export function QueuePositionDisplay({
  position,
  etaMinutes,
  leaveHomeBy,
  totalAhead,
  totalSeen,
  updatedAt,
}: QueuePositionDisplayProps) {
  const { t } = useI18n()
  const [ticking, setTicking] = useState(false)
  const previous = useRef(position)

  useEffect(() => {
    if (previous.current === position) return
    previous.current = position
    setTicking(true)
    const timer = setTimeout(() => setTicking(false), 300)
    return () => clearTimeout(timer)
  }, [position])

  // Recomputed on a timer rather than at render: nothing else re-renders this
  // component while a patient sits and watches it, so without the tick the
  // staleness warning would never appear on the screen that needs it most.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(timer)
  }, [])

  const ageMs = now - updatedAt.getTime()
  const isStale = ageMs > STALE_AFTER_MS

  return (
    <section className="rounded-lg border border-n200 bg-white p-6">
      <p className="text-label uppercase tracking-wide text-n600">
        {t("queue_title")}
      </p>

      <p className="mt-4 text-body-lg text-n700">{t("queue_you_are")}</p>
      <p
        className={[
          "text-display text-n900 tabular-nums",
          ticking && "animate-queue-tick",
        ]
          .filter(Boolean)
          .join(" ")}
        // The number changes underneath a patient who may not be looking at
        // it. Announce it politely rather than interrupting.
        aria-live="polite"
      >
        {position}
      </p>

      <p className="mt-2 text-body text-n600">
        {t("queue_people_waiting", { n: totalAhead })} ·{" "}
        {t("seen_today", { n: totalSeen })}
      </p>

      {/* The honesty branch. There is no third state here on purpose: either
          we have a live figure from the facility, or we say we do not. */}
      <p
        className={[
          "mt-4 text-body-lg",
          etaMinutes === null ? "text-n600" : "font-medium text-n900",
        ].join(" ")}
      >
        {etaMinutes === null
          ? t("queue_eta_unknown")
          : t("queue_eta_about", { minutes: etaMinutes })}
      </p>

      {/* Hidden entirely when unknown - never rendered empty. */}
      {leaveHomeBy !== null && (
        <p className="mt-3 inline-flex rounded-pill border border-accent/40 bg-accent/20 px-3 py-1.5 text-body-lg font-medium text-n900">
          {t("queue_leave_by", { time: leaveHomeBy })}
        </p>
      )}

      {isStale && (
        <p className="mt-4 text-body text-n700">
          {t("queue_updated_ago", { minutes: Math.floor(ageMs / 60000) })}
        </p>
      )}
    </section>
  )
}

export default QueuePositionDisplay
