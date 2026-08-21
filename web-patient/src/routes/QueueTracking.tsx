import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { useCurrentQueueEntry } from "../hooks/useQueue"
import { usePatient } from "../hooks/useAuth"
import { Card, Chip, EmptyState, ErrorState, ListSkeleton, Notice } from "../ui"
import { timeAgo } from "../lib/format"
import type { QueueEntryPublic } from "../api/types"

/**
 * Queue tracking, full screen.
 *
 * The whole product reduces to one sentence here:
 *
 *     "You are number 8. Leave home by 10:15."
 *
 * So `leave_by` is the largest thing after the position itself, and nothing
 * else is allowed onto the screen that would compete with those two facts.
 *
 * When `leave_by` is null - no home location, or no reliable statistics - the
 * line is HIDDEN rather than filled with a placeholder. A patient will act on
 * a time they are shown.
 */
export function QueueTracking() {
  const { t, lang } = useI18n()
  const patient = usePatient()
  const query = useCurrentQueueEntry(patient !== null)

  if (!patient) {
    return (
      <div className="ml-page py-6">
        <EmptyState
          title={t("sign_in_to_track")}
          action={
            <Link to="/sign-in" className="ml-btn-primary ml-btn-sm">
              {t("sign_in")}
            </Link>
          }
        />
      </div>
    )
  }

  if (query.isLoading) {
    return (
      <div className="ml-page py-6">
        <ListSkeleton rows={1} />
      </div>
    )
  }

  // Distinguished from "no active queue" on purpose. Telling somebody who IS
  // in a queue that they are not would send them home.
  if (query.isError) {
    return (
      <div className="ml-page py-6">
        <ErrorState
          title={t("queue_load_failed")}
          body={t("queue_load_failed_body")}
          action={
            <button
              className="ml-btn-secondary ml-btn-sm"
              onClick={() => query.refetch()}
            >
              {t("retry")}
            </button>
          }
        />
      </div>
    )
  }

  const entry = query.data
  if (!entry) {
    return (
      <div className="ml-page py-6">
        <EmptyState
          title={t("no_active_queue")}
          body={t("no_active_queue_body")}
          action={
            <Link to="/visits" className="ml-btn-secondary ml-btn-sm">
              {t("nav_visits")}
            </Link>
          }
        />
      </div>
    )
  }

  const called = entry.status === "called"

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24">
      <p className="text-center text-body text-ink-muted">
        {entry.facility.name}
      </p>

      <Card className="mt-3 px-6 py-8 text-center">
        {called ? <Called entry={entry} /> : <Waiting entry={entry} />}

        <p className="mt-6 text-caption text-ink-subtle">
          {t("updated_ago", { ago: timeAgo(entry.as_of, lang) })}
        </p>
      </Card>

      <div className="mt-4 flex gap-2">
        <a
          className="ml-btn-primary flex-1"
          href={`https://www.google.com/maps/dir/?api=1&destination=${entry.facility.location.lat},${entry.facility.location.lng}`}
          target="_blank"
          rel="noreferrer"
        >
          {t("directions")}
        </a>
        <Link
          to={`/facility/${entry.facility.slug}`}
          className="ml-btn-secondary flex-1"
        >
          {t("view_facility")}
        </Link>
      </div>

      {!called && entry.leave_by === null && (
        <div className="mt-4">
          {/* Why the departure time is missing, and how to get it. */}
          <Notice tone="info">
            {entry.eta_minutes === null
              ? t("leave_by_no_estimate")
              : t("leave_by_needs_home")}
          </Notice>
        </div>
      )}
    </div>
  )
}

function Waiting({ entry }: { entry: QueueEntryPublic }) {
  const { t } = useI18n()
  const ahead = entry.people_ahead ?? 0
  // Progress is illustrative only; the number is the fact.
  const total = Math.max(ahead + 1, 1)
  const done = Math.max(0, total - (entry.position ?? total))

  return (
    <>
      <p className="text-body text-ink-muted">{t("you_are_number")}</p>
      <p className="mt-1 text-queue font-semibold tabular-nums">
        {entry.position}
      </p>

      <div
        className="mx-auto mt-4 h-2 w-full max-w-xs overflow-hidden rounded-full bg-surface-sunken"
        role="progressbar"
        aria-valuenow={done}
        aria-valuemin={0}
        aria-valuemax={total}
      >
        <span
          className="block h-full rounded-full bg-primary transition-all"
          style={{ width: `${Math.round((done / total) * 100)}%` }}
        />
      </div>

      <p className="mt-4 text-body-lg text-ink-muted">
        {entry.eta_minutes === null
          ? t("wait_unavailable")
          : entry.eta_confidence === "low"
            ? t("eta_range", {
                low: Math.max(5, Math.round((entry.eta_minutes * 0.85) / 5) * 5),
                high: Math.round((entry.eta_minutes * 1.2) / 5) * 5,
              })
            : t("eta_about", {
                minutes: Math.max(5, Math.round(entry.eta_minutes / 5) * 5),
              })}
      </p>

      {/* The sentence the product exists for. */}
      {entry.leave_by && (
        <p className="mt-5 text-h1">
          {t("leave_home_by", {
            time: new Date(entry.leave_by).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
          })}
        </p>
      )}
    </>
  )
}

function Called({ entry }: { entry: QueueEntryPublic }) {
  const { t } = useI18n()
  return (
    <>
      <Chip tone="success">{t("called_now")}</Chip>
      <p className="mt-4 text-h1">{t("go_in_now")}</p>
      <p className="mt-2 font-mono text-h2 tracking-wide">{entry.ticket_code}</p>
    </>
  )
}
