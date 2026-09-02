import { Link } from "react-router-dom"
import { IconClock } from "../ui/icons"
import { useI18n } from "../i18n"
import { useCurrentQueueEntry } from "../hooks/useQueue"
import { useServiceTypes } from "../hooks/useNearbyFacilities"
import { usePatient } from "../hooks/useAuth"
import { Chip, EmptyState, ErrorState, ListSkeleton, Notice } from "../ui"
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
  const serviceTypes = useServiceTypes()

  if (!patient) {
    return (
      <div className="ml-page py-6">
        <h1 className="mb-4 text-h1">{t("queue_title")}</h1>
        <EmptyState icon={<IconClock size={20} />}
          title={t("sign_in_to_track")}
          action={
            <Link to={`/sign-in?next=${encodeURIComponent("/queue")}`} className="ml-btn-primary ml-btn-sm">
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
        {/* The same heading the signed-out branch above carries. Without it
            this was the one patient screen that rendered no h1 at all, so a
            screen reader landing here had nothing to orient on - and it was
            the empty state, which is exactly when you most need telling
            where you are. */}
        <h1 className="mb-4 text-h1">{t("queue_title")}</h1>
        <EmptyState icon={<IconClock size={20} />}
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

  /* `entry.service` is a code - it was rendering as "general_consultation"
     on the panel, under a facility name, in a Kinyarwanda interface. Resolve
     it to the translated name, and show nothing rather than the code if the
     lookup has not landed yet. */
  const serviceLabel =
    serviceTypes.data?.results.find((s) => s.code === entry.service)?.[
      `name_${lang}` as "name_rw" | "name_en" | "name_fr"
    ] ?? null

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24 md:pb-10">
      {/* Visually the facility name leads, but the page still has to SAY what
          it is - the position and the departure time below carry the weight,
          so the heading stays small rather than competing with them. */}
      <h1 className="sr-only">{t("queue_title")}</h1>

      {/* S-06, per docs/01_patient_app.html: a green panel carrying the
          position and the ticket, with the two facts a patient checks next
          - the wait and the place - as cards beneath it.

          Three things the spec draws that are NOT here, because the API
          cannot answer them and this screen does not invent: the "of 47"
          total, the assigned doctor, and the three-lane progress bar, which
          needs a seen/remaining split the queue entry does not carry. The
          dots below show people ahead instead, which is the same question a
          patient is actually asking and is countable at a glance. */}
      <section className="overflow-hidden rounded-lg bg-primary px-6 py-8 text-center text-white">
        <p className="text-body-lg text-white/80">
          {entry.facility.name}
          {serviceLabel ? ` · ${serviceLabel}` : ""}
        </p>

        {called ? <Called entry={entry} /> : <Waiting entry={entry} />}

        {entry.ticket_code && (
          <p className="mt-5 inline-flex items-center gap-2 rounded-pill bg-white/15 px-3 py-1.5 text-label">
            <span
              aria-hidden="true"
              className="h-2 w-2 rounded-full bg-success"
            />
            {t("queue_active")} · {t("ticket")}: {entry.ticket_code}
          </p>
        )}
      </section>

      {/* The two numbers a patient checks after the position itself. */}
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-n200 bg-white p-4">
          <p className="ml-label">{t("est_wait")}</p>
          {/* The honesty branch, again. Amber when we have a figure from the
              facility; muted and explicit when we do not. Never a guess. */}
          {entry.eta_minutes === null ? (
            <p className="mt-1 text-body text-n600">{t("queue_eta_unknown")}</p>
          ) : (
            <p className="mt-1 text-h2 tabular-nums text-n900">
              ~{entry.eta_minutes} min
            </p>
          )}
        </div>

        <div className="rounded-lg border border-n200 bg-white p-4">
          <p className="ml-label">{t("your_position")}</p>
          <p className="mt-1 text-h2 tabular-nums text-n900">
            {entry.position}
          </p>
        </div>
      </div>

      <p className="mt-3 text-center text-label text-n600">
        {t("updated_ago", { ago: timeAgo(entry.as_of, lang) })}
      </p>

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

  return (
    <>
      <p className="text-body-lg text-white/80">{t("you_are_number")}</p>
      <p className="mt-1 text-display tabular-nums">
        {entry.position}
      </p>

      {/* People, not a bar.
          A progress bar shows how far along you are, and somebody who has
          just joined is 0% along - so it rendered as an empty grey line that
          read as broken rather than as "nobody has been seen yet". Dots
          answer the question a patient actually has, which is "how many
          people are in front of me", and they are countable at a glance up
          to about a dozen. */}
      {ahead > 0 && (
        <div className="mt-5">
          <div
            className="mx-auto flex max-w-xs flex-wrap justify-center gap-1.5"
            role="img"
            aria-label={t("people_ahead", { n: ahead })}
          >
            {Array.from({ length: Math.min(ahead, 12) }, (_, i) => (
              <span
                key={i}
                aria-hidden="true"
                className="h-2 w-2 rounded-full bg-white/30"
              />
            ))}
            <span aria-hidden="true" className="h-2 w-2 rounded-full bg-white" />
          </div>
          <p className="mt-2.5 text-body text-white/80">
            {t("people_ahead", { n: ahead })}
          </p>
        </div>
      )}

      {/* Next in line is worth saying out loud rather than showing zero dots. */}
      {ahead === 0 && (
        <p className="mt-5 text-body-lg font-medium text-primary">
          {t("you_are_next")}
        </p>
      )}

      {/* The card below carries the estimate now, so the panel only speaks
          when there IS one - a range or an approximation is context for the
          number above it, whereas repeating "not available" twice on one
          screen reads as a fault rather than as honesty. */}
      <p className="mt-4 text-body-lg text-white/90">
        {entry.eta_minutes === null
          ? ""
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
