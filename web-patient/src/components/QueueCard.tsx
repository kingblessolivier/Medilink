import { useI18n } from "../i18n"
import { roundTo5, timeAgo } from "../lib/format"
import type { QueueEntryPublic } from "../api/types"

/**
 * Home screen state B - and the reason this product exists.
 *
 * When a queue entry is active this REPLACES the search hero. Nothing may
 * compete with it: the patient opened the app to learn one thing.
 */
export function QueueCard({
  entry,
  onCancel,
}: {
  entry: QueueEntryPublic
  onCancel?: () => void
}) {
  const { t, lang } = useI18n()

  const called = entry.status === "called"
  const total = Math.max(entry.position + entry.people_ahead, 1)
  const progress = Math.max(0, Math.min(1, 1 - entry.people_ahead / total))

  const directions =
    `https://www.google.com/maps/dir/?api=1&destination=` +
    `${entry.facility.location.lat},${entry.facility.location.lng}`

  return (
    <section className="ml-card mb-4 p-4 text-center">
      <p className="text-small text-ink-muted">{entry.facility.name}</p>

      {called ? (
        <p className="my-6 text-2xl font-semibold text-success">
          {t("queue_called_now", { ticket: entry.ticket_code })}
        </p>
      ) : (
        <>
          <p className="mt-4 text-small text-ink-muted">{t("queue_you_are")}</p>
          {/* Readable at arm's length, across a room, by an elderly patient. */}
          <p className="text-[4rem] font-bold leading-none">{entry.position}</p>

          <div
            className="mx-auto mt-4 h-2 w-full max-w-xs overflow-hidden rounded-full bg-surface-sunken"
            role="progressbar"
            aria-valuenow={Math.round(progress * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${progress * 100}%` }}
            />
          </div>

          <EtaLine entry={entry} />
          <LeaveByLine entry={entry} />
        </>
      )}

      <p className="mt-4 text-caption text-ink-subtle">
        {t("updated_ago", { ago: timeAgo(entry.as_of, lang) })}
      </p>

      <div className="mt-4 flex gap-2">
        <a
          className="ml-btn-secondary flex-1"
          href={directions}
          target="_blank"
          rel="noreferrer"
        >
          {t("directions")}
        </a>
        {onCancel && (
          <button className="ml-btn-secondary flex-1" onClick={onCancel}>
            {t("cancel")}
          </button>
        )}
      </div>
    </section>
  )
}

/**
 * Widen the wording as confidence falls. "About 35 min" claims a precision we
 * only have with a large sample behind it.
 */
function EtaLine({ entry }: { entry: QueueEntryPublic }) {
  const { t } = useI18n()

  if (entry.eta_minutes === null || entry.eta_minutes === undefined) {
    return (
      <p className="mt-4 text-small text-ink-muted">{t("queue_eta_unknown")}</p>
    )
  }

  const minutes = roundTo5(entry.eta_minutes)

  if (entry.eta_confidence === "low") {
    return (
      <p className="mt-4 text-base">
        {t("queue_eta_range", {
          from: Math.max(5, minutes - 10),
          to: minutes + 15,
        })}
      </p>
    )
  }

  return <p className="mt-4 text-base">{t("queue_eta_about", { minutes })}</p>
}

/**
 * The single most useful line in the product. Hidden entirely - never shown as
 * a placeholder - when we cannot compute it, because a patient would act on it.
 */
function LeaveByLine({ entry }: { entry: QueueEntryPublic }) {
  const { t } = useI18n()

  if (!entry.leave_by) {
    return (
      <p className="mt-2 text-caption text-ink-subtle">{t("queue_set_home")}</p>
    )
  }

  const depart = new Date(entry.leave_by)
  const leaveNow = depart.getTime() - Date.now() < 60_000

  if (leaveNow) {
    return (
      <p className="mt-3 rounded-lg bg-amber-50 py-2 text-base font-semibold text-warning">
        {t("queue_leave_now")}
      </p>
    )
  }

  return (
    <p className="mt-3 text-h2">
      {t("queue_leave_by", {
        time: depart.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      })}
    </p>
  )
}
